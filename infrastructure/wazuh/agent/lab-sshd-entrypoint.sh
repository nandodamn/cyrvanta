#!/bin/sh
# Cyrvanta lab agent entrypoint.
#
# Adds an SSH service to the stock Wazuh agent so the lab can produce real
# authentication telemetry -- failed and successful logins carrying a source IP
# -- which is what deterministic correlation groups on. File integrity events
# cannot serve that purpose: they have no source IP, so they never correlate.
#
# Lab only. The account exists to be attacked from another lab container.
set -e

LOG_FILE="/var/log/secure"
CREDENTIALS_FILE="/var/ossec/lab-ssh-credentials"
LAB_USER="${LAB_SSH_USER:-analista}"

if [ -n "${LAB_SSH_ENABLED:-}" ] && command -v /usr/sbin/sshd >/dev/null 2>&1; then
  ssh-keygen -A >/dev/null 2>&1 || true

  # The image ships with password auth disabled, so every password attempt is
  # rejected before it is evaluated and never produces "Failed password" -- the
  # line the Wazuh brute-force rules match on. A credential attack has to be
  # able to try passwords, so the lab enables it. Lab only.
  cat > /etc/ssh/sshd_config.d/00-cyrvanta-lab.conf <<'SSHCONF'
PasswordAuthentication yes
KbdInteractiveAuthentication no
SSHCONF

  if ! id "$LAB_USER" >/dev/null 2>&1; then
    useradd -m -s /bin/bash "$LAB_USER"
    # LAB_SSH_PASSWORD lets the demo console render a working login command
    # without ever reaching into this container: both read the same value from
    # .env, so there is nothing to query across the network. Falls back to a
    # generated one so the scenario still works if that variable is unset.
    # Either way the value lives in .env, never in the image or in compose.
    password="${LAB_SSH_PASSWORD:-$(head -c 18 /dev/urandom | base64 | tr -d '/+=' | cut -c1-16)}"
    printf '%s:%s\n' "$LAB_USER" "$password" | chpasswd
    printf 'usuario=%s\npassword=%s\n' "$LAB_USER" "$password" > "$CREDENTIALS_FILE"
    chmod 600 "$CREDENTIALS_FILE"
  fi

  # Syslog first, then sshd with no -E, so authentication lines land in
  # /var/log/secure carrying the prefix the Wazuh decoders match on.
  touch "$LOG_FILE"
  chmod 640 "$LOG_FILE"
  rm -f /var/run/rsyslogd.pid
  rsyslogd -f /etc/rsyslog-lab.conf 2>/dev/null || true
  # sshd opens its syslog connection at startup, so the socket has to exist
  # first or its authentication messages are lost for the life of the process.
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    [ -S /dev/log ] && break
    sleep 1
  done
  /usr/sbin/sshd
fi

# Point the agent at the authentication log. Idempotent, and applied before the
# agent starts so the first scan already includes it.
CONFIG="/var/ossec/etc/ossec.conf"

# Integrity and rootcheck scans default to every 12 hours, which is useless for
# a demo: a change made on stage would surface the next day. Set here rather
# than patched by hand, so a rebuild does not silently restore the default.
if [ -f "$CONFIG" ]; then
  sed -i "s|<frequency>43200</frequency>|<frequency>${LAB_SCAN_SECONDS:-60}</frequency>|g" "$CONFIG"
fi

if [ -f "$CONFIG" ] && ! grep -q "$LOG_FILE" "$CONFIG"; then
  python3 - "$CONFIG" "$LOG_FILE" <<'PY' || true
import sys

config_path, log_file = sys.argv[1], sys.argv[2]
with open(config_path, encoding="utf-8") as handle:
    content = handle.read()
stanza = (
    "  <localfile>\n"
    "    <log_format>syslog</log_format>\n"
    f"    <location>{log_file}</location>\n"
    "  </localfile>\n\n"
)
marker = "</ossec_config>"
if stanza not in content and marker in content:
    content = content.replace(marker, stanza + marker, 1)
    with open(config_path, "w", encoding="utf-8") as handle:
        handle.write(content)
PY
fi

exec /init "$@"
