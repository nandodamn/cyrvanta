"""A tenant's correlation rules must be invisible and untouchable to another.

Rules used to be global: one row decided what every tenant detected, which is
why rule administration could never be exposed to a tenant-scoped role. These
assert the isolation that replaced that, at both layers -- the database refuses
to show another tenant's rows, and the service refuses to act on them even when
handed an id that exists.
"""

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, text

from cyrvanta.modules.correlation.application.rule_admin import (
    CorrelationRuleAdminService,
    RuleVersionNotFound,
)
from cyrvanta.modules.correlation.infrastructure.models import CorrelationRuleVersionModel
from cyrvanta.modules.identity.infrastructure.models import AuditEventModel, UserModel
from cyrvanta.shared.database import SessionFactory, tenant_session


async def _tenants() -> list[UUID]:
    async with SessionFactory() as session, session.begin():
        await session.execute(text("SELECT set_config('app.auth_lookup', 'true', true)"))
        rows = await session.execute(text("SELECT id FROM tenants ORDER BY created_at, id"))
        return [row[0] for row in rows]


def _definition() -> dict:
    return {
        "grouping": "asset",
        "threshold": 85,
        "selectors": [
            {"code": "a", "field": "rule_reference", "value": "1", "source_system": "wazuh"},
            {"code": "b", "field": "rule_reference", "value": "2", "source_system": "wazuh"},
        ],
    }


@pytest_asyncio.fixture
async def two_tenants():
    tenants = await _tenants()
    if len(tenants) < 2:
        pytest.skip("isolation cannot be observed with a single tenant")
    code = f"test-isolation-{uuid4().hex[:10]}"
    yield tenants[0], tenants[1], code
    for tenant_id in tenants[:2]:
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
                        CorrelationRuleVersionModel.id.in_(ids)
                    )
                )


async def _actor(session, tenant_id: UUID) -> UUID:
    actor = await session.scalar(
        select(UserModel.id).where(UserModel.tenant_id == tenant_id).limit(1)
    )
    assert actor is not None
    return actor


@pytest.mark.asyncio
async def test_a_rule_published_by_one_tenant_is_invisible_to_the_other(two_tenants) -> None:
    owner, other, code = two_tenants
    async with tenant_session(owner) as session:
        service = CorrelationRuleAdminService(session)
        await service.create_draft(
            tenant_id=owner,
            actor_user_id=await _actor(session, owner),
            rule_code=code,
            version="1",
            definition=_definition(),
        )

    async with tenant_session(owner) as session:
        assert len(await CorrelationRuleAdminService(session).list_versions(owner, code)) == 1
    async with tenant_session(other) as session:
        assert await CorrelationRuleAdminService(session).list_versions(other, code) == []


@pytest.mark.asyncio
async def test_the_same_rule_code_can_exist_in_both_tenants_independently(two_tenants) -> None:
    """Two tenants naming a rule the same is not a collision. Before scoping,
    the unique constraint on (rule_code, version) made it one.
    """
    owner, other, code = two_tenants
    for tenant_id in (owner, other):
        async with tenant_session(tenant_id) as session:
            await CorrelationRuleAdminService(session).create_draft(
                tenant_id=tenant_id,
                actor_user_id=await _actor(session, tenant_id),
                rule_code=code,
                version="1",
                definition=_definition(),
            )
    for tenant_id in (owner, other):
        async with tenant_session(tenant_id) as session:
            rows = await CorrelationRuleAdminService(session).list_versions(tenant_id, code)
            assert [row.tenant_id for row in rows] == [tenant_id]


@pytest.mark.asyncio
async def test_a_tenant_cannot_activate_another_tenant_s_version(two_tenants) -> None:
    """Reported as absent rather than refused: whether another tenant's rule
    exists is not this tenant's business either.
    """
    owner, other, code = two_tenants
    async with tenant_session(owner) as session:
        draft = await CorrelationRuleAdminService(session).create_draft(
            tenant_id=owner,
            actor_user_id=await _actor(session, owner),
            rule_code=code,
            version="1",
            definition=_definition(),
        )
        foreign_id = draft.id

    async with tenant_session(other) as session:
        with pytest.raises(RuleVersionNotFound):
            await CorrelationRuleAdminService(session).activate(
                tenant_id=other,
                actor_user_id=await _actor(session, other),
                version_id=foreign_id,
            )


@pytest.mark.asyncio
async def test_row_level_security_hides_rules_without_a_tenant_context() -> None:
    """The service filters explicitly, but the database must not depend on it."""
    async with SessionFactory() as session, session.begin():
        visible = await session.scalar(text("SELECT count(*) FROM correlation_rule_versions"))
    assert visible == 0
