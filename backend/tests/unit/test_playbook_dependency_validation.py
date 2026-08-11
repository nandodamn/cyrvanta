from pathlib import Path


def test_dependency_validation_never_returns_partial_success_on_invalid_artifact() -> None:
    root = Path(__file__).parents[2] / "src" / "cyrvanta" / "modules" / "playbooks"
    service = (root / "application" / "administration_service.py").read_text(encoding="utf-8")
    router = (root / "presentation" / "administration_router.py").read_text(encoding="utf-8")

    method = service.split("async def validate_connection_dependencies", maxsplit=1)[1].split(
        "async def publish_version", maxsplit=1
    )[0]
    route = router.split("async def get_connection_dependencies", maxsplit=1)[1].split(
        '@router.post("/playbook-versions/{version_id}/publish"', maxsplit=1
    )[0]

    assert "except Exception" not in method
    assert 'PlaybookAdministrationConflict("PLAYBOOK_INVALID")' in method
    assert "except PlaybookAdministrationConflict" in route
