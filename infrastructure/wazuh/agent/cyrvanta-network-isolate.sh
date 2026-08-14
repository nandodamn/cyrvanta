#!/bin/sh
# Cyrvanta network isolation active-response script.
#
# Wazuh Active Response protocol: wazuh-execd writes exactly one JSON line to
# this script's stdin, but -- confirmed empirically with a diagnostic
# wrapper -- it never closes/EOFs that pipe. `INPUT_JSON=$(cat)` (or any
# EOF-driven read) therefore hangs forever, leaving a zombie process and
# silently dropping every isolate/restore call. Read exactly one line with
# `read` instead, which returns on the newline without waiting for EOF.
#
# "add"    -> drop all inbound/outbound traffic on this host except loopback
#             and the Wazuh manager (so the agent stays reachable for the
#             eventual restore command).
# "delete" -> remove the block and restore normal connectivity.
#
# This is the script cyrvanta.modules.playbooks.infrastructure.action_registry
# invokes (via the Wazuh Manager API PUT /active-response) for the
# host.isolate / host.restore native playbook actions.

set -eu

LOG_FILE=/var/ossec/logs/active-responses.log
CHAIN=CYRVANTA_ISOLATE

log() {
  printf '%s cyrvanta-network-isolate: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" >> "$LOG_FILE" 2>/dev/null || true
}

IFS= read -r INPUT_JSON
log "raw AR payload: ${INPUT_JSON}"
# Cyrvanta always drives this script via the API "arguments" list
# (delivered as parameters.extra_args), not Wazuh's own add/delete timeout
# state machine -- host.isolate/host.restore are explicit, independent calls.
COMMAND=$(printf '%s' "$INPUT_JSON" | python3 -c 'import json,sys
try:
    data = json.load(sys.stdin)
    extra_args = data.get("parameters", {}).get("extra_args", [])
    print(extra_args[0] if extra_args else data.get("command", ""))
except Exception:
    print("")')

MANAGER_HOST="${WAZUH_MANAGER_SERVER:-wazuh-manager}"
MANAGER_IP=$(getent hosts "$MANAGER_HOST" 2>/dev/null | awk '{print $1}' | head -n1 || true)

case "$COMMAND" in
  add)
    log "isolating host (manager_ip=${MANAGER_IP:-unknown})"
    iptables -N "$CHAIN" 2>/dev/null || iptables -F "$CHAIN"
    iptables -A "$CHAIN" -o lo -j ACCEPT
    iptables -A "$CHAIN" -i lo -j ACCEPT
    if [ -n "$MANAGER_IP" ]; then
      iptables -A "$CHAIN" -d "$MANAGER_IP" -j ACCEPT
      iptables -A "$CHAIN" -s "$MANAGER_IP" -j ACCEPT
    fi
    iptables -A "$CHAIN" -j DROP
    iptables -C OUTPUT -j "$CHAIN" 2>/dev/null || iptables -I OUTPUT 1 -j "$CHAIN"
    iptables -C INPUT -j "$CHAIN" 2>/dev/null || iptables -I INPUT 1 -j "$CHAIN"
    log "isolation applied"
    ;;
  delete)
    log "restoring host network"
    iptables -D OUTPUT -j "$CHAIN" 2>/dev/null || true
    iptables -D INPUT -j "$CHAIN" 2>/dev/null || true
    iptables -F "$CHAIN" 2>/dev/null || true
    iptables -X "$CHAIN" 2>/dev/null || true
    log "isolation reverted"
    ;;
  *)
    log "unrecognized command in AR payload: '${COMMAND}'"
    exit 1
    ;;
esac

exit 0
