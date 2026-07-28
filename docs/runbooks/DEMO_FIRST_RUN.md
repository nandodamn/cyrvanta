# Cyrvanta demo — first-run runbook

Status: internal acceptance must pass before following this runbook.

## Safety boundary

The bundled attack is synthetic. It does not scan, exploit, or modify any external host.
OpenSearch, Wazuh, Ollama, and n8n default to clearly labelled simulation mode. Switching
an adapter to `live` requires deployment-specific credentials and security review.

## Demo identity

Use the tenant slug and full-access demo credentials supplied out of band during local
bootstrap. Never commit credentials to this repository. The demo identity is tenant-scoped;
it is not a cross-tenant platform administrator.

## Acceptance

From PowerShell at the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\acceptance.ps1
```

Do not begin a demonstration unless the last line is `CYRVANTA_ACCEPTANCE_OK`.

## Safe walkthrough

1. Sign in locally.
2. Generate the credential-attack scenario from Overview.
3. Inspect the four alerts and the linked incident.
4. Advance the incident through its audited lifecycle.
5. Request the bounded AI analysis and review deterministic risk plus ATT&CK mappings.
6. Simulate the explicitly approved allowlisted response.
7. Download the incident HTML report.
8. Review adapter status under Integrations and audit events under Administration.

LDAP/Active Directory can remain unconfigured until an enterprise directory or isolated
directory lab is available. Local break-glass access remains independent of LDAP.
