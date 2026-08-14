from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, select, text

from cyrvanta.modules.identity.infrastructure.models import AuditEventModel, UserModel
from cyrvanta.modules.playbooks.application.engine_ports import EngineContext
from cyrvanta.modules.playbooks.infrastructure.action_registry import ActionRegistry
from cyrvanta.shared.database import SessionFactory, tenant_session


async def _existing_tenant_and_actor() -> tuple[UUID, UUID]:
    async with SessionFactory() as session, session.begin():
        await session.execute(text("SELECT set_config('app.auth_lookup', 'true', true)"))
        tenant_id = (await session.execute(text("SELECT id FROM tenants LIMIT 1"))).scalar()
        actor_id = (await session.execute(text("SELECT id FROM users LIMIT 1"))).scalar()
    return tenant_id, actor_id


@asynccontextmanager
async def _target_user(tenant_id: UUID):
    async with tenant_session(tenant_id) as session:
        user = UserModel(
            id=uuid4(),
            tenant_id=tenant_id,
            email=f"containment-{uuid4().hex[:8]}@example.test",
            password_hash="x",
            display_name="Containment Test User",
            is_active=True,
        )
        session.add(user)
        await session.flush()
        user_id = user.id
    try:
        yield user_id
    finally:
        async with tenant_session(tenant_id) as session:
            await session.execute(
                delete(AuditEventModel).where(AuditEventModel.resource_id == user_id)
            )
            await session.execute(delete(UserModel).where(UserModel.id == user_id))


def _context(tenant_id: UUID) -> EngineContext:
    return EngineContext(
        tenant_id=tenant_id, correlation_id=uuid4(), causation_id=None, deadline=datetime.now(UTC)
    )


async def test_account_disable_deactivates_user_and_returns_snapshot() -> None:
    tenant_id, actor_id = await _existing_tenant_and_actor()
    async with _target_user(tenant_id) as target_id:
        connector = ActionRegistry().get("account.disable", "1.0.0")
        context = _context(tenant_id)

        result = await connector.execute(
            context,
            {"inputs": {"target_user_id": str(target_id), "actor_user_id": str(actor_id)}},
            {},
            "idem-disable-1",
            None,
        )

        assert result.succeeded is True
        assert result.output["effect"] == "applied"
        assert result.output["snapshot"]["was_active"] is True

        async with tenant_session(tenant_id) as session:
            user = await session.get(UserModel, target_id)
            assert user is not None
            assert user.is_active is False
            event = await session.scalar(
                select(AuditEventModel).where(
                    AuditEventModel.tenant_id == tenant_id,
                    AuditEventModel.resource_id == target_id,
                    AuditEventModel.action == "user.account.disabled",
                )
            )
            assert event is not None
            assert event.details["snapshot"]["was_active"] is True


async def test_account_disable_is_idempotent_for_same_correlation() -> None:
    tenant_id, actor_id = await _existing_tenant_and_actor()
    async with _target_user(tenant_id) as target_id:
        connector = ActionRegistry().get("account.disable", "1.0.0")
        context = _context(tenant_id)
        inputs = {"inputs": {"target_user_id": str(target_id), "actor_user_id": str(actor_id)}}

        first = await connector.execute(context, inputs, {}, "idem-disable-2", None)
        second = await connector.execute(context, inputs, {}, "idem-disable-2", None)

        assert first.succeeded is True and first.output["effect"] == "applied"
        assert second.succeeded is True and second.output["effect"] == "idempotent"

        async with tenant_session(tenant_id) as session:
            count = await session.scalar(
                select(AuditEventModel.id).where(
                    AuditEventModel.tenant_id == tenant_id,
                    AuditEventModel.resource_id == target_id,
                    AuditEventModel.action == "user.account.disabled",
                )
            )
            assert count is not None


async def test_account_disable_fails_closed_on_nonempty_configuration() -> None:
    tenant_id, actor_id = await _existing_tenant_and_actor()
    async with _target_user(tenant_id) as target_id:
        connector = ActionRegistry().get("account.disable", "1.0.0")
        context = _context(tenant_id)

        result = await connector.execute(
            context,
            {"inputs": {"target_user_id": str(target_id), "actor_user_id": str(actor_id)}},
            {"unexpected": "value"},
            "idem-disable-3",
            None,
        )

        assert result.succeeded is False
        assert result.error_code == "PLAYBOOK_ACTION_CONFIG_INVALID"

        async with tenant_session(tenant_id) as session:
            user = await session.get(UserModel, target_id)
            assert user.is_active is True


async def test_account_enable_requires_prior_disable_event() -> None:
    tenant_id, actor_id = await _existing_tenant_and_actor()
    async with _target_user(tenant_id) as target_id:
        connector = ActionRegistry().get("account.enable", "1.0.0")
        context = _context(tenant_id)

        result = await connector.execute(
            context,
            {
                "inputs": {
                    "target_user_id": str(target_id),
                    "actor_user_id": str(actor_id),
                    "original_execution_id": str(uuid4()),
                }
            },
            {},
            "idem-enable-1",
            None,
        )

        assert result.succeeded is False
        assert result.error_code == "PLAYBOOK_STATE_CONFLICT"


async def test_account_enable_reactivates_previously_disabled_user() -> None:
    tenant_id, actor_id = await _existing_tenant_and_actor()
    async with _target_user(tenant_id) as target_id:
        disable = ActionRegistry().get("account.disable", "1.0.0")
        enable = ActionRegistry().get("account.enable", "1.0.0")
        disable_result = await disable.execute(
            _context(tenant_id),
            {"inputs": {"target_user_id": str(target_id), "actor_user_id": str(actor_id)}},
            {},
            "idem-disable-4",
            None,
        )
        original_execution_id = disable_result.output["receipt"]

        enable_result = await enable.execute(
            _context(tenant_id),
            {
                "inputs": {
                    "target_user_id": str(target_id),
                    "actor_user_id": str(actor_id),
                    "original_execution_id": original_execution_id,
                }
            },
            {},
            "idem-enable-2",
            None,
        )

        assert enable_result.succeeded is True
        assert enable_result.output["effect"] == "applied"

        async with tenant_session(tenant_id) as session:
            user = await session.get(UserModel, target_id)
            assert user.is_active is True
            event = await session.scalar(
                select(AuditEventModel).where(
                    AuditEventModel.tenant_id == tenant_id,
                    AuditEventModel.resource_id == target_id,
                    AuditEventModel.action == "user.account.enabled",
                )
            )
            assert event is not None
            assert event.details["original_execution_id"] == original_execution_id
