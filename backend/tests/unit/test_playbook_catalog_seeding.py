from uuid import UUID

from sqlalchemy import text

from cyrvanta.modules.playbooks.application.administration_service import (
    ESSENTIAL_NATIVE_PLAYBOOKS,
    PlaybookAdministrationService,
)
from cyrvanta.shared.database import SessionFactory


async def _existing_tenant_id() -> UUID:
    async with SessionFactory() as session, session.begin():
        await session.execute(text("SELECT set_config('app.auth_lookup', 'true', true)"))
        return (await session.execute(text("SELECT id FROM tenants LIMIT 1"))).scalar()


async def test_list_definitions_seeds_the_full_essential_catalog() -> None:
    """
    Regression test: _ensure_essential_definitions_seeded previously violated
    ck_playbook_version_validation (validated_sha256/validated_at were set
    without validated_by_user_id) and called a non-existent self._record_audit
    method, so list_definitions() raised on every tenant's first call and the
    playbook library never populated. This exercises the real seeding path
    against real Postgres, not just the in-memory catalog constants.
    """
    tenant_id = await _existing_tenant_id()
    service = PlaybookAdministrationService()

    result = await service.list_definitions(tenant_id, limit=100, offset=0)

    essential_codes = {str(item["code"]) for item in ESSENTIAL_NATIVE_PLAYBOOKS}
    returned_codes = {item.code for item in result.items}
    assert essential_codes <= returned_codes
    assert result.total >= len(essential_codes)

    # Calling it again must be idempotent (no duplicate versions/definitions).
    second = await service.list_definitions(tenant_id, limit=100, offset=0)
    assert second.total == result.total
