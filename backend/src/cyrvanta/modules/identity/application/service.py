from datetime import timedelta
from uuid import UUID

from pwdlib import PasswordHash
from redis.asyncio import Redis
from sqlalchemy import select, text

from cyrvanta.modules.identity.application.schemas import (
    CurrentUserResponse,
    LoginRequest,
    TokenResponse,
)
from cyrvanta.modules.identity.application.tokens import TokenService
from cyrvanta.modules.identity.infrastructure.models import AuditEventModel, TenantModel, UserModel
from cyrvanta.shared.config import get_settings
from cyrvanta.shared.database import SessionFactory, tenant_session


class AuthenticationError(Exception):
    pass


class AuthenticationService:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        self.passwords = PasswordHash.recommended()
        self.tokens = TokenService()
        self.settings = get_settings()

    async def login(self, request: LoginRequest, correlation_id: UUID) -> TokenResponse:
        async with SessionFactory() as session, session.begin():
            await session.execute(text("SELECT set_config('app.auth_lookup', 'true', true)"))
            user = await session.scalar(
                select(UserModel)
                .join(TenantModel, TenantModel.id == UserModel.tenant_id)
                .where(
                    TenantModel.slug == request.tenant_slug,
                    UserModel.email == request.email.lower(),
                )
            )
        if (
            user is None
            or not user.is_active
            or not self.passwords.verify(request.password, user.password_hash)
        ):
            if user is not None:
                await self._audit(user, "auth.login", correlation_id, outcome="failure")
            raise AuthenticationError
        response = await self.issue_user(user, request.remember_me)
        await self._audit(user, "auth.login", correlation_id)
        return response

    async def refresh(self, refresh_token: str) -> TokenResponse:
        digest = self.tokens.refresh_digest(refresh_token)
        session_value = await self.redis.get(f"refresh:{digest}")
        if session_value is None:
            raise AuthenticationError
        session_parts = session_value.decode().split("|", 3)
        user_id_raw, tenant_id_raw, email = session_parts[:3]
        remember_me = len(session_parts) == 4 and session_parts[3] == "1"
        await self.redis.delete(f"refresh:{digest}")
        await self.redis.srem(f"user_refresh:{user_id_raw}", digest)  # type: ignore[misc]
        user = UserModel(
            id=UUID(user_id_raw),
            tenant_id=UUID(tenant_id_raw),
            email=email,
            display_name="",
            password_hash="",
        )
        return await self.issue_user(user, remember_me)

    async def logout(self, refresh_token: str) -> None:
        digest = self.tokens.refresh_digest(refresh_token)
        value = await self.redis.get(f"refresh:{digest}")
        await self.redis.delete(f"refresh:{digest}")
        if value is not None:
            user_id = value.decode().split("|", 1)[0]
            await self.redis.srem(f"user_refresh:{user_id}", digest)  # type: ignore[misc]

    async def current_user(self, user_id: UUID, tenant_id: UUID) -> CurrentUserResponse:
        async with tenant_session(tenant_id) as session:
            user = await session.scalar(select(UserModel).where(UserModel.id == user_id))
            if user is None:
                raise AuthenticationError
            return CurrentUserResponse.model_validate(user)

    async def issue_user(self, user: UserModel, remember_me: bool = False) -> TokenResponse:
        refresh = self.tokens.new_refresh_token()
        digest = self.tokens.refresh_digest(refresh)
        ttl = timedelta(days=self.settings.refresh_token_ttl_days)
        await self.redis.setex(
            f"refresh:{digest}",
            int(ttl.total_seconds()),
            f"{user.id}|{user.tenant_id}|{user.email}|{int(remember_me)}",
        )
        await self.redis.sadd(f"user_refresh:{user.id}", digest)  # type: ignore[misc]
        await self.redis.expire(f"user_refresh:{user.id}", int(ttl.total_seconds()))
        return TokenResponse(
            access_token=self.tokens.create_access_token(user.id, user.tenant_id, user.email),
            refresh_token=refresh,
            remember_me=remember_me,
        )

    async def _audit(
        self, user: UserModel, action: str, correlation_id: UUID, outcome: str = "success"
    ) -> None:
        async with tenant_session(user.tenant_id) as session:
            session.add(
                AuditEventModel(
                    tenant_id=user.tenant_id,
                    actor_user_id=user.id,
                    action=action,
                    resource_type="session",
                    outcome=outcome,
                    correlation_id=correlation_id,
                    details={},
                )
            )
