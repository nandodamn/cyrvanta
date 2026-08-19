# Cyrvanta lab Wazuh agent: the stock wazuh/wazuh-agent image plus iptables
# (needed for real network isolation) and the cyrvanta-network-isolate
# active-response script used by the host.isolate / host.restore native
# playbook actions (see backend/src/cyrvanta/modules/playbooks/infrastructure/action_registry.py).
FROM wazuh/wazuh-agent:4.14.6

USER root

# openssh-server lets the lab produce real authentication telemetry. Findings
# from file integrity monitoring carry no source IP, so they can never satisfy a
# correlation rule that groups by it -- login attempts can.
# The client is what lets one lab host attempt logins against another, so the
# resulting telemetry carries a real source IP instead of loopback. rsyslog is
# required, not cosmetic: sshd's own -E output has no syslog prefix, and the
# Wazuh sshd decoders match on that prefix, so authentication lines written
# without it are read and then silently discarded.
# sshpass is what lets the scenario attack the account it later breaks into.
# Without it the failures have to target a user that does not exist, and the
# story stops being a credential attack: failing as one user and succeeding as
# another are two unrelated events that merely share a source address.
# sudo is what makes privilege escalation observable. Wazuh recognises the
# escalation from sudo's own authpriv log lines (rules 5401/5402/5403/5404);
# with no sudo installed those lines never exist, so a rule selecting them
# would load cleanly and then detect nothing.
RUN dnf install -y iptables openssh-server openssh-clients rsyslog sshpass sudo && dnf clean all

COPY cyrvanta-network-isolate.sh /var/ossec/active-response/bin/cyrvanta-network-isolate
RUN chown root:wazuh /var/ossec/active-response/bin/cyrvanta-network-isolate \
    && chmod 750 /var/ossec/active-response/bin/cyrvanta-network-isolate

# Container-appropriate syslog routing. The distribution default reads local
# messages through the systemd journal, which does not exist here, so /dev/log
# was never created and authentication messages never reached disk.
COPY lab-rsyslog.conf /etc/rsyslog-lab.conf

# Starts syslog and sshd, then points the agent at the authentication log before
# handing over to the stock init, so the agent watches it from its first scan.
COPY lab-sshd-entrypoint.sh /usr/local/bin/cyrvanta-lab-entrypoint
RUN chmod 755 /usr/local/bin/cyrvanta-lab-entrypoint
ENTRYPOINT ["/usr/local/bin/cyrvanta-lab-entrypoint"]
