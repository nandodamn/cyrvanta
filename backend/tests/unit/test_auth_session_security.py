from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from cyrvanta.modules.identity.application import service as auth_module
from cyrvanta.modules.identity.application.service import (
    AuthenticationError,
    AuthenticationService,
)
from cyrvanta.shared import dependencies


def credentials() -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials="signed-token")


@pytest.mark.parametrize("active_user", [None, uuid4()])
async def test_security_context_revalidates_active_user(
    monkeypatch: pytest.MonkeyPatch, active_user: object | None
) -> None:
    user_id, tenant_id = uuid4(), uuid4()
    token_service = SimpleNamespace(
        decode_access_token=lambda _token: {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "email": "analyst@example.test",
        }
    )
    session = SimpleNamespace(scalar=AsyncMock(return_value=active_user))

    @asynccontextmanager
    async def session_scope(scoped_tenant_id):
        assert scoped_tenant_id == tenant_id
        yield session

    monkeypatch.setattr(dependencies, "TokenService", lambda: token_service)
    monkeypatch.setattr(dependencies, "tenant_session", session_scope)

    if active_user is None:
        with pytest.raises(HTTPException) as denied:
            await dependencies.get_security_context(credentials())
        assert denied.value.status_code == 401
    else:
        context = await dependencies.get_security_context(credentials())
        assert context.user_id == user_id
        assert context.tenant_id == tenant_id


async def test_refresh_rotation_is_single_use_and_generation_guarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, tenant_id = uuid4(), uuid4()
    user = SimpleNamespace(
        id=user_id,
        tenant_id=tenant_id,
        email="analyst@example.test",
        is_active=True,
    )
    old_token = "r" * 64
    old_digest = AuthenticationService._decode_redis_value(
        auth_module.TokenService.refresh_digest(old_token)
    )
    old_record = f"{user_id}|{tenant_id}|{user.email}|1|7"
    redis = AsyncMock()
    redis.get.return_value = old_record.encode()
    redis.eval.side_effect = [1, 0]
    service = object.__new__(AuthenticationService)
    service.redis = redis
    service.tokens = auth_module.TokenService()
    service.settings = SimpleNamespace(refresh_token_ttl_days=7)

    session = SimpleNamespace(scalar=AsyncMock(return_value=user))

    @asynccontextmanager
    async def session_scope(scoped_tenant_id):
        assert scoped_tenant_id == tenant_id
        yield session

    monkeypatch.setattr(auth_module, "tenant_session", session_scope)

    first = await service.refresh(old_token)
    with pytest.raises(AuthenticationError):
        await service.refresh(old_token)

    assert first.remember_me is True
    assert redis.eval.await_count == 2
    first_rotation = redis.eval.await_args_list[0].args
    assert first_rotation[0] == auth_module.ROTATE_REFRESH_SCRIPT
    assert first_rotation[1] == 4
    assert first_rotation[3] == f"refresh:{old_digest}"
    assert first_rotation[6] == old_record
    assert first_rotation[7] == "7"


async def test_session_revocation_advances_generation_before_deleting_tokens() -> None:
    from cyrvanta.modules.identity.application.administration_service import (
        AdministrationService,
    )

    user_id = uuid4()
    redis = AsyncMock()
    redis.smembers.return_value = {b"digest"}
    service = object.__new__(AdministrationService)
    service.redis = redis

    await service._revoke_refresh_tokens(user_id)

    assert redis.mock_calls[0].args == (f"user_refresh_generation:{user_id}",)
    assert redis.mock_calls[0][0] == "incr"
