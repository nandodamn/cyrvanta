from cyrvanta.shared.config import Settings


def test_external_integrations_use_secure_defaults() -> None:
    defaults = {
        name: field.default
        for name, field in Settings.model_fields.items()
    }

    assert defaults["opensearch_mode"] == "simulated"
    assert defaults["wazuh_mode"] == "simulated"
    assert defaults["ollama_mode"] == "simulated"
    assert defaults["n8n_mode"] == "disabled"
    assert defaults["n8n_enabled"] is False
    assert defaults["playbook_native_engine_enabled"] is True
    assert defaults["playbook_live_enabled"] is False
    assert defaults["playbook_dispatch_enabled"] is False


def test_default_n8n_allowlist_contains_only_approved_workflows() -> None:
    raw_allowlist = Settings.model_fields["n8n_allowed_workflow_ids"].default

    assert isinstance(raw_allowlist, str)
    assert set(raw_allowlist.split(",")) == {
        "cyrvanta-simulate-user-block",
        "notify-critical-incident",
        "create-security-ticket",
        "request-dual-approval",
        "incident-report-email",
    }
