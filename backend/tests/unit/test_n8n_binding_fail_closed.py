from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from cyrvanta.modules.playbooks.application.administration_service import (
    PlaybookAdministrationConflict,
    PlaybookAdministrationService,
)


def _binding(**overrides):
    values = {
        "sync_status": "SYNCHRONIZED",
        "last_verified_at": datetime(2026, 8, 11, tzinfo=UTC),
        "desired_digest": "a" * 64,
        "observed_digest": "a" * 64,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize(
    "binding",
    [
        _binding(sync_status="PENDING", last_verified_at=None, observed_digest=None),
        _binding(sync_status="UNAVAILABLE", observed_digest=None),
        _binding(last_verified_at=None),
    ],
)
def test_unverified_binding_cannot_be_activated(binding) -> None:
    with pytest.raises(PlaybookAdministrationConflict, match="PLAYBOOK_BINDING_UNAVAILABLE"):
        PlaybookAdministrationService._assert_binding_activatable(binding)


def test_drifted_binding_cannot_be_activated() -> None:
    with pytest.raises(PlaybookAdministrationConflict, match="PLAYBOOK_BINDING_DRIFTED"):
        PlaybookAdministrationService._assert_binding_activatable(
            _binding(observed_digest="b" * 64)
        )


def test_verified_matching_binding_can_be_activated() -> None:
    PlaybookAdministrationService._assert_binding_activatable(_binding())


def test_toggle_does_not_fabricate_a_local_n8n_instance() -> None:
    source = (
        Path(__file__).parents[2]
        / "src"
        / "cyrvanta"
        / "modules"
        / "playbooks"
        / "application"
        / "administration_service.py"
    ).read_text(encoding="utf-8")

    assert 'instance_code="local-demo"' not in source
    assert 'key_id="local-demo-v1"' not in source
    assert "self.settings.n8n_enabled and bool(self.settings.n8n_api_key)" not in source
