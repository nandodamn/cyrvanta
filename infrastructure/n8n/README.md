# Cyrvanta n8n workflows

This directory is the source of truth for managed n8n workflow artifacts.
Artifacts remain inactive in Git. Reconciliation may activate only a released
synthetic workflow whose digest matches its tenant binding. LIVE workflows need
a separate operational approval.

`simulate-user-block` `1.0.0` replaces the provisional
`cyrvanta-demo-response` artifact. The legacy JSON remains in Git for the
documented compatibility window, but Compose no longer imports or activates it.

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
