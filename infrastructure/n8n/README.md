# Cyrvanta n8n workflows

This directory is the source of truth for managed n8n workflow artifacts.
Artifacts remain inactive in Git. Reconciliation may activate only a released
workflow whose digest matches its tenant binding. LIVE workflows need a
separate operational approval.

**The manifest is empty, and that is the shipped state.** n8n is the extension
point for integrations Cyrvanta has no native connector for; nothing is plugged
into it yet. It previously held five synthetic demo artifacts -- four webhooks
that answered "fail closed" and one that reported a simulated success -- which
demonstrated the mechanism and could not do anything. A product that ships
workflows unable to act teaches an operator that dispatching one is theatre.

The mechanism itself is unchanged: declare a workflow in `manifest.json` with
its digest, its schemas and its credential aliases, put the artifact under
`workflows/`, and reconcile.

Run `python infrastructure/n8n/scripts/validate_workflows.py` before import.
Credentials are referenced by aliases in `manifest.json`; secret values never
belong in Git or workflow JSON.

`scripts/reconcile.py` performs a read-only diff by default. `--apply` may
create, update, activate, or deactivate managed workflows, but never deletes
workflows, credentials, execution history, or the n8n volume. It requires
an explicit host-side `N8N_API_URL` plus `N8N_API_KEY`; it never derives the
host URL from the container-side `N8N_BASE_URL`. Connector aliases are supplied
separately through
`N8N_CREDENTIAL_ALIASES_JSON`.
