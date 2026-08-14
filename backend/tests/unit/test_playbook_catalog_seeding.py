from uuid import UUID

from sqlalchemy import select, text

from cyrvanta.modules.playbooks.application.administration_service import (
    ESSENTIAL_NATIVE_ACTIONS,
    ESSENTIAL_NATIVE_PLAYBOOKS,
    RETIRED_PLAYBOOK_CODES,
    PlaybookAdministrationService,
    catalog_step_actions,
)
from cyrvanta.modules.playbooks.infrastructure.models import (
    AutomationEngineBindingModel,
    NativeActionBindingModel,
    PlaybookDefinitionModel,
    PlaybookVersionModel,
)
from cyrvanta.shared.database import SessionFactory, tenant_session


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


async def _seeded_artifact(tenant_id: UUID, code: str) -> dict:
    async with tenant_session(tenant_id) as session:
        definition = await session.scalar(
            select(PlaybookDefinitionModel).where(
                PlaybookDefinitionModel.tenant_id == tenant_id,
                PlaybookDefinitionModel.code == code,
            )
        )
        assert definition is not None
        version = await session.scalar(
            select(PlaybookVersionModel)
            .where(
                PlaybookVersionModel.tenant_id == tenant_id,
                PlaybookVersionModel.definition_id == definition.id,
                PlaybookVersionModel.status == "APPROVED",
            )
            .order_by(PlaybookVersionModel.created_at.desc())
        )
        assert version is not None
        return version.portable_artifact or {}


async def test_multi_step_playbook_chains_its_steps_on_success() -> None:
    """A failed containment must not be followed by the rest of the procedure.

    contain-and-document-incident isolates, reports, then marks the incident
    contained. Chaining on ALWAYS (or emitting no edges at all, which leaves
    every step unconditioned) would let the report and the "contained" status
    run even when the isolation step failed, reporting a containment that
    never happened.
    """
    tenant_id = await _existing_tenant_id()
    service = PlaybookAdministrationService()
    await service.list_definitions(tenant_id, limit=100, offset=0)

    artifact = await _seeded_artifact(tenant_id, "contain-and-document-incident")

    actions = [step["action"] for step in artifact["steps"] if step["type"] == "ACTION"]
    assert actions == list(catalog_step_actions("contain-and-document-incident"))
    assert actions[0] == "host.isolate"

    edges = artifact["edges"]
    assert len(edges) == len(actions) - 1
    assert {edge["outcome"] for edge in edges} == {"SUCCESS"}
    # Every step after the first must be reachable only from its predecessor.
    for position, edge in enumerate(edges, start=1):
        assert edge["from_step"] == f"step-{position}"
        assert edge["to_step"] == f"step-{position + 1}"
    # The overall deadline has to cover every step, not just one.
    assert artifact["timeouts"]["overall_seconds"] >= (
        artifact["timeouts"]["action_seconds"] * len(actions)
    )


async def test_catalog_text_is_refreshed_for_existing_tenants() -> None:
    """A stale description outlives the procedure it described.

    Seeding used to fill the description only when blank, so a tenant that
    already had the playbook kept the old summary after a remap -- still
    advertising steps the playbook no longer runs.
    """
    tenant_id = await _existing_tenant_id()
    service = PlaybookAdministrationService()
    await service.list_definitions(tenant_id, limit=100, offset=0)

    async with tenant_session(tenant_id) as session:
        definition = await session.scalar(
            select(PlaybookDefinitionModel).where(
                PlaybookDefinitionModel.tenant_id == tenant_id,
                PlaybookDefinitionModel.code == "contain-and-document-incident",
            )
        )
        assert definition is not None
        definition.description_es = "Texto viejo que ya no describe el procedimiento."
        definition.name_es = "Nombre viejo"

    await service.list_definitions(tenant_id, limit=100, offset=0)

    catalog = next(
        item
        for item in ESSENTIAL_NATIVE_PLAYBOOKS
        if item["code"] == "contain-and-document-incident"
    )
    async with tenant_session(tenant_id) as session:
        refreshed = await session.scalar(
            select(PlaybookDefinitionModel).where(
                PlaybookDefinitionModel.tenant_id == tenant_id,
                PlaybookDefinitionModel.code == "contain-and-document-incident",
            )
        )
    assert refreshed is not None
    assert refreshed.description_es == catalog["description_es"]
    assert refreshed.name_es == catalog["title_es"]


async def test_remapped_playbook_leaves_no_armed_predecessor() -> None:
    """Seeding a replacement must also disarm the version it replaces.

    Creating the new version alone left the old one APPROVED with an active
    binding, so the superseded procedure stayed dispatchable -- and since a
    remapped playbook usually needs integrations the old one did not, the
    weaker version was the only one a tenant could actually run.
    """
    tenant_id = await _existing_tenant_id()
    service = PlaybookAdministrationService()
    await service.list_definitions(tenant_id, limit=100, offset=0)

    async with tenant_session(tenant_id) as session:
        definition = await session.scalar(
            select(PlaybookDefinitionModel).where(
                PlaybookDefinitionModel.tenant_id == tenant_id,
                PlaybookDefinitionModel.code == "contain-and-document-incident",
            )
        )
        assert definition is not None
        versions = list(
            (
                await session.scalars(
                    select(PlaybookVersionModel).where(
                        PlaybookVersionModel.tenant_id == tenant_id,
                        PlaybookVersionModel.definition_id == definition.id,
                        PlaybookVersionModel.classification == "LIVE",
                    )
                )
            ).all()
        )
        expected = list(catalog_step_actions("contain-and-document-incident"))
        for version in versions:
            actions = [
                step["action"]
                for step in (version.portable_artifact or {}).get("steps", [])
                if step.get("type") == "ACTION"
            ]
            if actions == expected:
                continue
            assert version.status == "RETIRED", (
                f"superseded version {version.version} still {version.status}"
            )
            armed = await session.scalar(
                select(AutomationEngineBindingModel.id).where(
                    AutomationEngineBindingModel.tenant_id == tenant_id,
                    AutomationEngineBindingModel.playbook_version_id == version.id,
                    AutomationEngineBindingModel.active.is_(True),
                )
            )
            assert armed is None, f"superseded version {version.version} is still armed"


async def test_external_system_playbooks_stay_disarmed_until_configured() -> None:
    """No integration configured means the playbook must not present as ready.

    These four hand an approved incident to a third-party system (mail security,
    firewall, EDR, evidence vault). Seeding must not arm them on the tenant's
    behalf: an armed playbook with no destination would only fail once a real
    incident tried to use it.
    """
    tenant_id = await _existing_tenant_id()
    service = PlaybookAdministrationService()

    result = await service.list_definitions(tenant_id, limit=100, offset=0)
    by_code = {item.code: item for item in result.items}

    for code in (
        "phishing-malicious-email",
        "malicious-indicator",
        "security-control-disabled",
        "evidence-preservation",
    ):
        action_code = ESSENTIAL_NATIVE_ACTIONS[code]
        async with tenant_session(tenant_id) as session:
            binding = await session.scalar(
                select(NativeActionBindingModel).where(
                    NativeActionBindingModel.tenant_id == tenant_id,
                    NativeActionBindingModel.action_code == action_code,
                    NativeActionBindingModel.active.is_(True),
                    NativeActionBindingModel.last_verified_at.is_not(None),
                )
            )
        if binding is not None:
            continue  # This environment really did configure it; nothing to assert.
        assert by_code[code].readiness_status != "READY", (
            f"{code} reports ready without a verified {action_code} binding"
        )


async def test_retired_playbooks_are_neither_listed_nor_left_approved() -> None:
    """Retiring a catalog code must also disarm versions already seeded.

    Dropping the code from the catalog alone would leave existing tenants with
    an APPROVED version they could still dispatch.
    """
    tenant_id = await _existing_tenant_id()
    service = PlaybookAdministrationService()

    result = await service.list_definitions(tenant_id, limit=100, offset=0)

    assert RETIRED_PLAYBOOK_CODES.isdisjoint({item.code for item in result.items})
    async with tenant_session(tenant_id) as session:
        retired_versions = select(PlaybookVersionModel.id).join(
            PlaybookDefinitionModel,
            PlaybookDefinitionModel.id == PlaybookVersionModel.definition_id,
        ).where(
            PlaybookVersionModel.tenant_id == tenant_id,
            PlaybookDefinitionModel.code.in_(RETIRED_PLAYBOOK_CODES),
        )
        live = await session.scalars(
            select(PlaybookVersionModel.status)
            .join(
                PlaybookDefinitionModel,
                PlaybookDefinitionModel.id == PlaybookVersionModel.definition_id,
            )
            .where(
                PlaybookVersionModel.tenant_id == tenant_id,
                PlaybookDefinitionModel.code.in_(RETIRED_PLAYBOOK_CODES),
            )
        )
        assert set(live.all()) <= {"RETIRED"}
        # Status alone does not stop a dispatch -- the binding is what arms it.
        armed = await session.scalar(
            select(AutomationEngineBindingModel.id).where(
                AutomationEngineBindingModel.tenant_id == tenant_id,
                AutomationEngineBindingModel.playbook_version_id.in_(retired_versions),
                AutomationEngineBindingModel.active.is_(True),
            )
        )
        assert armed is None


async def test_catalog_playbooks_never_keep_a_synthetic_version_armed() -> None:
    """A demo artifact armed on a real playbook fakes the response.

    Running it would report a simulated success while nothing happened, which
    is the failure mode the catalog rework exists to remove. Demo playbooks of
    their own keep their own definitions and are untouched.
    """
    tenant_id = await _existing_tenant_id()
    service = PlaybookAdministrationService()
    await service.list_definitions(tenant_id, limit=100, offset=0)

    catalog_codes = [str(item["code"]) for item in ESSENTIAL_NATIVE_PLAYBOOKS]
    async with tenant_session(tenant_id) as session:
        armed_synthetic = await session.scalar(
            select(PlaybookVersionModel.id)
            .join(
                PlaybookDefinitionModel,
                PlaybookDefinitionModel.id == PlaybookVersionModel.definition_id,
            )
            .join(
                AutomationEngineBindingModel,
                AutomationEngineBindingModel.playbook_version_id == PlaybookVersionModel.id,
            )
            .where(
                PlaybookVersionModel.tenant_id == tenant_id,
                PlaybookVersionModel.classification == "SYNTHETIC",
                PlaybookDefinitionModel.code.in_(catalog_codes),
                AutomationEngineBindingModel.active.is_(True),
            )
        )
    assert armed_synthetic is None
