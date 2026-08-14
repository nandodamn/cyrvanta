from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
from sqlalchemy import delete, select, text

from cyrvanta.modules.identity.infrastructure.models import AuditEventModel
from cyrvanta.modules.integrations.application.connection_service import (
    StoredIntegrationCredential,
)
from cyrvanta.modules.playbooks.application.engine_ports import EngineContext
from cyrvanta.modules.playbooks.infrastructure.action_registry import ActionRegistry
from cyrvanta.shared.database import SessionFactory, tenant_session

_AGENT_ID_PREFIX = "999"


async def _existing_tenant_and_actor() -> tuple[UUID, UUID]:
    async with SessionFactory() as session, session.begin():
        await session.execute(text("SELECT set_config('app.auth_lookup', 'true', true)"))
        tenant_id = (await session.execute(text("SELECT id FROM tenants LIMIT 1"))).scalar()
        actor_id = (await session.execute(text("SELECT id FROM users LIMIT 1"))).scalar()
    return tenant_id, actor_id


def _context(tenant_id: UUID) -> EngineContext:
    return EngineContext(
        tenant_id=tenant_id, correlation_id=uuid4(), causation_id=None, deadline=datetime.now(UTC)
    )


def _credential() -> StoredIntegrationCredential:
    return StoredIntegrationCredential(
        reference="wazuh-primary",
        values={
            "base_url": "https://wazuh.test:55000",
            "username": "wazuh-user",
            "password": "wazuh-pass",
            "timeout_seconds": 5,
        },
    )


def _wazuh_ok_handler(calls: list[httpx.Request]):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith("/security/user/authenticate"):
            return httpx.Response(200, text="mock-bearer-token")
        if request.url.path.endswith("/active-response"):
            agent_id = request.url.params.get("agents_list", "")
            return httpx.Response(
                200,
                json={
                    "data": {
                        "affected_items": [agent_id],
                        "total_affected_items": 1,
                        "total_failed_items": 0,
                        "failed_items": [],
                    },
                    "message": "AR command was sent to agent",
                    "error": 0,
                },
                headers={"X-Request-Id": "wazuh-task-1"},
            )
        return httpx.Response(404)

    return handler


def _patch_httpx(monkeypatch, handler) -> None:
    real_async_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs.pop("verify", None)
        return real_async_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr("httpx.AsyncClient", factory)


async def _cleanup_agent_events(tenant_id: UUID, agent_id: str) -> None:
    async with tenant_session(tenant_id) as session:
        await session.execute(
            delete(AuditEventModel).where(
                AuditEventModel.tenant_id == tenant_id,
                AuditEventModel.action.in_(("host.network.isolated", "host.network.restored")),
                AuditEventModel.details["target_agent_id"].astext == agent_id,
            )
        )


async def test_host_isolate_sends_active_response_command_and_records_audit(monkeypatch) -> None:
    tenant_id, actor_id = await _existing_tenant_and_actor()
    agent_id = f"{_AGENT_ID_PREFIX}-{uuid4().hex[:6]}"
    try:
        calls: list[httpx.Request] = []
        _patch_httpx(monkeypatch, _wazuh_ok_handler(calls))
        connector = ActionRegistry().get("host.isolate", "1.0.0")
        context = _context(tenant_id)

        result = await connector.execute(
            context,
            {"inputs": {"target_agent_id": agent_id, "actor_user_id": str(actor_id)}},
            {},
            "idem-isolate-1",
            _credential(),
        )

        assert result.succeeded is True
        assert result.output["wazuh_task_id"] == "wazuh-task-1"
        assert any(
            req.method == "PUT" and req.url.path.endswith("/active-response") for req in calls
        )
        assert any(
            req.method == "GET" and req.url.path.endswith("/security/user/authenticate")
            for req in calls
        )

        async with tenant_session(tenant_id) as session:
            event = await session.scalar(
                select(AuditEventModel).where(
                    AuditEventModel.tenant_id == tenant_id,
                    AuditEventModel.action == "host.network.isolated",
                    AuditEventModel.correlation_id == context.correlation_id,
                )
            )
            assert event is not None
            assert event.details["target_agent_id"] == agent_id
    finally:
        await _cleanup_agent_events(tenant_id, agent_id)


async def test_host_isolate_is_idempotent_for_same_correlation(monkeypatch) -> None:
    tenant_id, actor_id = await _existing_tenant_and_actor()
    agent_id = f"{_AGENT_ID_PREFIX}-{uuid4().hex[:6]}"
    try:
        calls: list[httpx.Request] = []
        _patch_httpx(monkeypatch, _wazuh_ok_handler(calls))
        connector = ActionRegistry().get("host.isolate", "1.0.0")
        context = _context(tenant_id)
        inputs = {"inputs": {"target_agent_id": agent_id, "actor_user_id": str(actor_id)}}

        first = await connector.execute(context, inputs, {}, "idem-isolate-2", _credential())
        second = await connector.execute(context, inputs, {}, "idem-isolate-2", _credential())

        assert first.output["effect"] == "applied"
        assert second.succeeded is True
        assert second.output["effect"] == "idempotent"
    finally:
        await _cleanup_agent_events(tenant_id, agent_id)


async def test_host_isolate_fails_closed_without_wazuh_credential() -> None:
    tenant_id, actor_id = await _existing_tenant_and_actor()
    agent_id = f"{_AGENT_ID_PREFIX}-{uuid4().hex[:6]}"
    connector = ActionRegistry().get("host.isolate", "1.0.0")

    result = await connector.execute(
        _context(tenant_id),
        {"inputs": {"target_agent_id": agent_id, "actor_user_id": str(actor_id)}},
        {},
        "idem-isolate-3",
        None,
    )

    assert result.succeeded is False
    assert result.error_code == "PLAYBOOK_CREDENTIAL_UNAVAILABLE"


async def test_host_restore_requires_prior_isolate_event() -> None:
    tenant_id, actor_id = await _existing_tenant_and_actor()
    agent_id = f"{_AGENT_ID_PREFIX}-{uuid4().hex[:6]}"
    connector = ActionRegistry().get("host.restore", "1.0.0")

    result = await connector.execute(
        _context(tenant_id),
        {
            "inputs": {
                "target_agent_id": agent_id,
                "actor_user_id": str(actor_id),
                "original_execution_id": str(uuid4()),
            }
        },
        {},
        "idem-restore-1",
        _credential(),
    )

    assert result.succeeded is False
    assert result.error_code == "PLAYBOOK_STATE_CONFLICT"


async def test_host_restore_sends_restore_command_after_prior_isolation(monkeypatch) -> None:
    tenant_id, actor_id = await _existing_tenant_and_actor()
    agent_id = f"{_AGENT_ID_PREFIX}-{uuid4().hex[:6]}"
    try:
        calls: list[httpx.Request] = []
        _patch_httpx(monkeypatch, _wazuh_ok_handler(calls))
        isolate = ActionRegistry().get("host.isolate", "1.0.0")
        restore = ActionRegistry().get("host.restore", "1.0.0")

        isolate_result = await isolate.execute(
            _context(tenant_id),
            {"inputs": {"target_agent_id": agent_id, "actor_user_id": str(actor_id)}},
            {},
            "idem-restore-2",
            _credential(),
        )
        original_execution_id = isolate_result.output["receipt"]

        restore_result = await restore.execute(
            _context(tenant_id),
            {
                "inputs": {
                    "target_agent_id": agent_id,
                    "actor_user_id": str(actor_id),
                    "original_execution_id": original_execution_id,
                }
            },
            {},
            "idem-restore-3",
            _credential(),
        )

        assert restore_result.succeeded is True
        assert restore_result.output["effect"] == "applied"

        async with tenant_session(tenant_id) as session:
            event = await session.scalar(
                select(AuditEventModel).where(
                    AuditEventModel.tenant_id == tenant_id,
                    AuditEventModel.action == "host.network.restored",
                    AuditEventModel.details["target_agent_id"].astext == agent_id,
                )
            )
            assert event is not None
            assert event.details["original_execution_id"] == original_execution_id
    finally:
        await _cleanup_agent_events(tenant_id, agent_id)
