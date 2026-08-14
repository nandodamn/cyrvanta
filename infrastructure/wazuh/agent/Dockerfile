# Cyrvanta lab Wazuh agent: the stock wazuh/wazuh-agent image plus iptables
# (needed for real network isolation) and the cyrvanta-network-isolate
# active-response script used by the host.isolate / host.restore native
# playbook actions (see backend/src/cyrvanta/modules/playbooks/infrastructure/action_registry.py).
FROM wazuh/wazuh-agent:4.14.6

USER root

RUN dnf install -y iptables && dnf clean all

COPY cyrvanta-network-isolate.sh /var/ossec/active-response/bin/cyrvanta-network-isolate
RUN chown root:wazuh /var/ossec/active-response/bin/cyrvanta-network-isolate \
    && chmod 750 /var/ossec/active-response/bin/cyrvanta-network-isolate
