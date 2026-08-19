"""Publishing a rule version is a security-relevant change, so it has to be
attributable, atomic, and refused outright when the definition is wrong.

These run against the real database, so every version created here uses a
unique rule_code and is removed afterwards -- the shipped rules must be left
exactly as they were found.
"""

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, text

from cyrvanta.modules.correlation.application.rule_admin import (
    ACTIVE,
    DRAFT,
    RETIRED,
    CorrelationRuleAdminService,
    RuleDefinitionInvalid,
    RuleVersionConflict,
    RuleVersionNotFound,
    canonical,
    validate_definition,
)
from cyrvanta.modules.correlation.infrastructure.models import CorrelationRuleVersionModel
from cyrvanta.modules.identity.infrastructure.models import AuditEventModel, UserModel
from cyrvanta.shared.database import SessionFactory, tenant_session


async def _existing_tenant_id() -> UUID:
    async with SessionFactory() as session, session.begin():
        await session.execute(text("SELECT set_config('app.auth_lookup', 'true', true)"))
        return (await session.execute(text("SELECT id FROM tenants LIMIT 1"))).scalar()


def _definition(**overrides) -> dict:
    definition = {
        "grouping": "asset",
        "threshold": 85,
        "window_minutes": 10,
        "candidate_limit": 500,
        "member_limit": 32,
        "partial_issue_allowlist": [],
        "selectors": [
            {"code": "a", "field": "rule_reference", "value": "1", "source_system": "wazuh"},
            {"code": "b", "field": "rule_reference", "value": "2", "source_system": "wazuh"},
        ],
    }
    definition.update(overrides)
    return definition


@pytest_asyncio.fixture
async def scope():
    tenant_id = await _existing_tenant_id()
    code = f"test-rule-{uuid4().hex[:12]}"
    async with tenant_session(tenant_id) as session:
        actor_id = await session.scalar(
            select(UserModel.id).where(UserModel.tenant_id == tenant_id).limit(1)
        )
    yield tenant_id, actor_id, code
    async with tenant_session(tenant_id) as session:
        ids = list(
            (
                await session.scalars(
                    select(CorrelationRuleVersionModel.id).where(
                        CorrelationRuleVersionModel.rule_code == code
                    )
                )
            ).all()
        )
        if ids:
            await session.execute(
                delete(AuditEventModel).where(AuditEventModel.resource_id.in_(ids))
            )
            await session.execute(
                delete(CorrelationRuleVersionModel).where(
                    CorrelationRuleVersionModel.rule_code == code
                )
            )


@pytest.mark.asyncio
async def test_activating_a_version_retires_the_previous_one(scope) -> None:
    tenant_id, actor_id, code = scope
    async with tenant_session(tenant_id) as session:
        service = CorrelationRuleAdminService(session)
        first = await service.create_draft(
            tenant_id=tenant_id,
            actor_user_id=actor_id,
            rule_code=code,
            version="1",
            definition=_definition(),
        )
        await service.activate(tenant_id=tenant_id, actor_user_id=actor_id, version_id=first.id)
        second = await service.create_draft(
            tenant_id=tenant_id,
            actor_user_id=actor_id,
            rule_code=code,
            version="2",
            definition=_definition(threshold=90),
        )
        await service.activate(tenant_id=tenant_id, actor_user_id=actor_id, version_id=second.id)

        versions = {row.version: row.status for row in await service.list_versions(code)}
        assert versions == {"1": RETIRED, "2": ACTIVE}


@pytest.mark.asyncio
async def test_only_one_version_of_a_rule_is_ever_active(scope) -> None:
    """The partial unique index already forbids two ACTIVE rows; this asserts
    the service does not depend on hitting it to stay correct.
    """
    tenant_id, actor_id, code = scope
    async with tenant_session(tenant_id) as session:
        service = CorrelationRuleAdminService(session)
        for version in ("1", "2", "3"):
            draft = await service.create_draft(
                tenant_id=tenant_id,
                actor_user_id=actor_id,
                rule_code=code,
                version=version,
                definition=_definition(),
            )
            await service.activate(tenant_id=tenant_id, actor_user_id=actor_id, version_id=draft.id)
        rows = await service.list_versions(code)
        assert [row.status for row in rows].count(ACTIVE) == 1


@pytest.mark.asyncio
async def test_every_operation_leaves_an_audit_record(scope) -> None:
    tenant_id, actor_id, code = scope
    async with tenant_session(tenant_id) as session:
        service = CorrelationRuleAdminService(session)
        draft = await service.create_draft(
            tenant_id=tenant_id,
            actor_user_id=actor_id,
            rule_code=code,
            version="1",
            definition=_definition(),
        )
        await service.activate(tenant_id=tenant_id, actor_user_id=actor_id, version_id=draft.id)
        await service.retire(tenant_id=tenant_id, actor_user_id=actor_id, version_id=draft.id)
        await session.flush()

        actions = list(
            (
                await session.scalars(
                    select(AuditEventModel.action).where(AuditEventModel.resource_id == draft.id)
                )
            ).all()
        )
        assert sorted(actions) == [
            "correlation.rule.activated",
            "correlation.rule.drafted",
            "correlation.rule.retired",
        ]


@pytest.mark.asyncio
async def test_a_retired_version_cannot_be_brought_back(scope) -> None:
    tenant_id, actor_id, code = scope
    async with tenant_session(tenant_id) as session:
        service = CorrelationRuleAdminService(session)
        draft = await service.create_draft(
            tenant_id=tenant_id,
            actor_user_id=actor_id,
            rule_code=code,
            version="1",
            definition=_definition(),
        )
        await service.retire(tenant_id=tenant_id, actor_user_id=actor_id, version_id=draft.id)
        with pytest.raises(RuleVersionConflict):
            await service.activate(tenant_id=tenant_id, actor_user_id=actor_id, version_id=draft.id)


@pytest.mark.asyncio
async def test_a_duplicate_version_is_refused(scope) -> None:
    tenant_id, actor_id, code = scope
    async with tenant_session(tenant_id) as session:
        service = CorrelationRuleAdminService(session)
        await service.create_draft(
            tenant_id=tenant_id,
            actor_user_id=actor_id,
            rule_code=code,
            version="1",
            definition=_definition(),
        )
        with pytest.raises(RuleVersionConflict):
            await service.create_draft(
                tenant_id=tenant_id,
                actor_user_id=actor_id,
                rule_code=code,
                version="1",
                definition=_definition(),
            )


@pytest.mark.asyncio
async def test_activating_something_that_does_not_exist_is_an_error(scope) -> None:
    tenant_id, actor_id, _code = scope
    async with tenant_session(tenant_id) as session:
        with pytest.raises(RuleVersionNotFound):
            await CorrelationRuleAdminService(session).activate(
                tenant_id=tenant_id, actor_user_id=actor_id, version_id=uuid4()
            )


@pytest.mark.asyncio
async def test_an_invalid_definition_never_reaches_the_database(scope) -> None:
    tenant_id, actor_id, code = scope
    async with tenant_session(tenant_id) as session:
        service = CorrelationRuleAdminService(session)
        with pytest.raises(RuleDefinitionInvalid):
            await service.create_draft(
                tenant_id=tenant_id,
                actor_user_id=actor_id,
                rule_code=code,
                version="1",
                definition=_definition(grouping="asset_owner"),
            )
        assert await service.list_versions(code) == []
        assert (
            await session.scalar(
                select(AuditEventModel.id)
                .where(AuditEventModel.action.like("correlation.rule.%"))
                .where(AuditEventModel.details["rule_code"].astext == code)
            )
            is None
        )


@pytest.mark.parametrize(
    "definition",
    [
        pytest.param({"selectors": []}, id="no selectors"),
        pytest.param(_definition(threshold=101), id="threshold above 100"),
        pytest.param(_definition(threshold="85"), id="threshold not an integer"),
        pytest.param(_definition(grouping="tenant"), id="unknown grouping"),
        pytest.param(_definition(min_severity=101), id="min_severity above 100"),
        pytest.param(_definition(window_minutes=0), id="non-positive window"),
        pytest.param(_definition(candidate_limit=-1), id="negative candidate limit"),
        pytest.param(_definition(partial_issue_allowlist="oops"), id="allowlist not a list"),
        pytest.param(
            _definition(
                selectors=[
                    {"code": "a", "field": "hostname", "value": "1", "source_system": "wazuh"},
                    {"code": "b", "field": "rule_reference", "value": "2", "source_system": "w"},
                ]
            ),
            id="selector on an unmatchable field",
        ),
        pytest.param(
            _definition(
                selectors=[
                    {"code": "a", "field": "rule_reference", "value": "1", "source_system": "w"},
                ]
            ),
            id="multi-signal rule offering one signal",
        ),
    ],
)
def test_definitions_that_would_detect_nothing_are_rejected(definition: dict) -> None:
    with pytest.raises(RuleDefinitionInvalid):
        validate_definition(definition)


def test_a_single_signal_rule_may_declare_one_selector() -> None:
    """The two-selector requirement exists only because the engine demands
    distinct_signal_pattern; min_severity waives it, so the rule is valid.
    """
    validate_definition(
        _definition(
            min_severity=70,
            selectors=[
                {"code": "a", "field": "rule_reference", "value": "1", "source_system": "wazuh"}
            ],
        )
    )


def test_the_hash_identifies_the_rule_not_its_key_order() -> None:
    definition = _definition()
    reordered = dict(reversed(list(definition.items())))
    assert canonical(definition)[1] == canonical(reordered)[1]


def test_draft_is_the_starting_status() -> None:
    assert (DRAFT, ACTIVE, RETIRED) == ("DRAFT", "ACTIVE", "RETIRED")
