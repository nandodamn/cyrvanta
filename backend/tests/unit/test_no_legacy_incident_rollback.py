from pathlib import Path


def test_legacy_incident_rollback_route_and_bulk_mutation_are_absent() -> None:
    source_root = Path(__file__).parents[2] / "src" / "cyrvanta" / "modules" / "incident"
    service = (source_root / "application" / "service.py").read_text(encoding="utf-8")
    router = (source_root / "presentation" / "router.py").read_text(encoding="utf-8")

    assert "async def execute_rollback" not in service
    assert "UPDATE users SET is_active" not in service
    assert "UPDATE action_proposals SET status = 'ROLLED_BACK'" not in service
    assert '"/incidents/{incident_id}/rollback"' not in router
