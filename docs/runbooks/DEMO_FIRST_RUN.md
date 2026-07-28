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
5. Open the incident and review its evidence-backed ATT&CK mappings, five
   deterministic risk factors and bilingual explanation.
6. Optionally request an `AIProvider` rewrite. If Ollama is cold, the first
   Gemma 4 response can take longer; the deterministic explanation remains
   available and authoritative.
7. Simulate the explicitly approved allowlisted response.
8. Download the incident HTML report.
9. Review adapter status under Integrations and audit events under Administration.

LDAP/Active Directory can remain unconfigured until an enterprise directory or isolated
directory lab is available. Local break-glass access remains independent of LDAP.
