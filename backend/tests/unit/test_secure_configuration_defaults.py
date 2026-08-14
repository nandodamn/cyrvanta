import base64

import pytest
from pydantic import ValidationError

from cyrvanta.shared.config import Settings


def test_external_integrations_use_secure_defaults() -> None:
    defaults = {name: field.default for name, field in Settings.model_fields.items()}

    assert defaults["opensearch_mode"] == "disabled"
    assert defaults["wazuh_mode"] == "disabled"
    assert defaults["ollama_mode"] == "disabled"
    assert defaults["n8n_mode"] == "disabled"
    assert defaults["n8n_enabled"] is False
    assert defaults["playbook_native_engine_enabled"] is True
    assert defaults["playbook_live_enabled"] is False
    assert defaults["playbook_dispatch_enabled"] is False
    assert defaults["decision_automatic_response_enabled"] is False


def test_default_n8n_allowlist_contains_only_approved_workflows() -> None:
    raw_allowlist = Settings.model_fields["n8n_allowed_workflow_ids"].default

    assert isinstance(raw_allowlist, str)
    assert set(raw_allowlist.split(",")) == {
        "cyrvanta-simulate-user-block",
        "cyrvanta-notify-critical-incident",
        "cyrvanta-create-security-ticket",
        "cyrvanta-request-dual-approval",
        "cyrvanta-incident-report-email",
    }


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "frontend_url": "https://cyrvanta.example",
        "cors_origins": "https://cyrvanta.example",
        "database_url": "postgresql+asyncpg://app:strong-password@postgres:5432/cyrvanta",
        "rabbitmq_url": "amqp://app:strong-password@rabbitmq:5672/",
        "jwt_secret": "a-production-jwt-secret-with-more-than-32-characters",
        "integration_encryption_key": base64.urlsafe_b64encode(b"x" * 32).decode(),
        "session_cookie_secure": True,
    }
    return Settings(**(values | overrides))


def test_valid_production_security_configuration_is_accepted() -> None:
    settings = production_settings()

    assert settings.secure_session_cookie is True


@pytest.mark.parametrize(
    "override",
    [
        {"database_url": "postgresql+asyncpg://app:change-me@postgres/cyrvanta"},
        {"rabbitmq_url": "amqp://guest:guest@rabbitmq:5672/"},
        {"jwt_secret": "replace-with-at-least-32-random-characters"},
        {"session_cookie_secure": False},
        {"cors_origins": "*"},
        {"cors_origins": "http://cyrvanta.example"},
        {"frontend_url": "http://cyrvanta.example"},
        {"integration_encryption_key": "A" * 44},
    ],
)
def test_production_rejects_unsafe_security_configuration(
    override: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        production_settings(**override)


def test_ai_timeout_covers_a_cold_model_load() -> None:
    """Regression: redaction was dropped silently whenever the model was cold.

    Inference against a resident model takes about 25s, but Ollama evicts an
    idle model after five minutes, and paging a multi-gigabyte model back in
    measured 121s-151s. The old 120s budget therefore expired mid-load, and
    because the provider turns any failure into None, the explanation was lost
    without a trace -- precisely in the sporadic-incident pattern a SOC has.
    """
    defaults = {name: field.default for name, field in Settings.model_fields.items()}

    # Must leave real headroom over an observed cold load, not just inference.
    assert defaults["ai_request_timeout_seconds"] >= 300

    # Asking Ollama to retain the model is what keeps that cold load rare.
    keep_alive = defaults["ollama_keep_alive"]
    assert isinstance(keep_alive, str)
    assert keep_alive.strip() not in ("", "0", "0s")
