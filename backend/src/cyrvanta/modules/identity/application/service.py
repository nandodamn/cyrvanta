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

ISSUE_REFRESH_SCRIPT = """
local current_generation = redis.call('GET', KEYS[1]) or '0'
if current_generation ~= ARGV[1] then return 0 end
redis.call('SETEX', KEYS[2], tonumber(ARGV[2]), ARGV[3])
redis.call('SADD', KEYS[3], ARGV[4])
redis.call('EXPIRE', KEYS[3], tonumber(ARGV[2]))
return 1
"""

ROTATE_REFRESH_SCRIPT = """
if redis.call('GET', KEYS[2]) ~= ARGV[1] then return 0 end
local current_generation = redis.call('GET', KEYS[1]) or '0'
if current_generation ~= ARGV[2] then return 0 end
redis.call('DEL', KEYS[2])
redis.call('SREM', KEYS[4], ARGV[5])
redis.call('SETEX', KEYS[3], tonumber(ARGV[3]), ARGV[4])
redis.call('SADD', KEYS[4], ARGV[6])
redis.call('EXPIRE', KEYS[4], tonumber(ARGV[3]))
return 1
"""


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
        encoded_session = self._decode_redis_value(session_value)
        user_id, tenant_id, _email, remember_me, generation = self._session_record(encoded_session)
        async with tenant_session(tenant_id) as session:
            user = await session.scalar(
                select(UserModel).where(
                    UserModel.tenant_id == tenant_id,
                    UserModel.id == user_id,
                    UserModel.is_active.is_(True),
                )
            )
        if user is None:
            raise AuthenticationError
        return await self.issue_user(
            user,
            remember_me,
            expected_generation=generation,
            replaces=(digest, encoded_session),
        )

    async def logout(self, refresh_token: str) -> None:
        digest = self.tokens.refresh_digest(refresh_token)
        value = await self.redis.getdel(f"refresh:{digest}")
        if value is not None:
            try:
                user_id, *_rest = self._session_record(self._decode_redis_value(value))
            except AuthenticationError:
                return
            await self.redis.srem(f"user_refresh:{user_id}", digest)  # type: ignore[misc]

    async def current_user(self, user_id: UUID, tenant_id: UUID) -> CurrentUserResponse:
        async with tenant_session(tenant_id) as session:
            user = await session.scalar(
                select(UserModel).where(
                    UserModel.tenant_id == tenant_id,
                    UserModel.id == user_id,
                    UserModel.is_active.is_(True),
                )
            )
            if user is None:
                raise AuthenticationError
            return CurrentUserResponse.model_validate(user)

    async def issue_user(
        self,
        user: UserModel,
        remember_me: bool = False,
        *,
        expected_generation: int | None = None,
        replaces: tuple[str, str] | None = None,
    ) -> TokenResponse:
        generation = (
            await self._session_generation(user.id)
            if expected_generation is None
            else expected_generation
        )
        refresh = self.tokens.new_refresh_token()
        digest = self.tokens.refresh_digest(refresh)
        ttl_seconds = int(timedelta(days=self.settings.refresh_token_ttl_days).total_seconds())
        session_value = f"{user.id}|{user.tenant_id}|{user.email}|{int(remember_me)}|{generation}"
        generation_key = f"user_refresh_generation:{user.id}"
        index_key = f"user_refresh:{user.id}"
        if replaces is None:
            created = await self.redis.eval(  # type: ignore[misc]
                ISSUE_REFRESH_SCRIPT,
                3,
                generation_key,
                f"refresh:{digest}",
                index_key,
                str(generation),
                str(ttl_seconds),
                session_value,
                digest,
            )
        else:
            old_digest, old_value = replaces
            created = await self.redis.eval(  # type: ignore[misc]
                ROTATE_REFRESH_SCRIPT,
                4,
                generation_key,
                f"refresh:{old_digest}",
                f"refresh:{digest}",
                index_key,
                old_value,
                str(generation),
                str(ttl_seconds),
                session_value,
                old_digest,
                digest,
            )
        if int(created) != 1:
            raise AuthenticationError
        return TokenResponse(
            access_token=self.tokens.create_access_token(user.id, user.tenant_id, user.email),
            refresh_token=refresh,
            remember_me=remember_me,
        )

    async def _session_generation(self, user_id: UUID) -> int:
        value = await self.redis.get(f"user_refresh_generation:{user_id}")
        if value is None:
            return 0
        try:
            return int(self._decode_redis_value(value))
        except ValueError as exc:
            raise AuthenticationError from exc

    @staticmethod
    def _decode_redis_value(value: bytes | str) -> str:
        return value.decode() if isinstance(value, bytes) else value

    @staticmethod
    def _session_record(value: str) -> tuple[UUID, UUID, str, bool, int]:
        parts = value.split("|")
        if len(parts) not in {4, 5}:
            raise AuthenticationError
        try:
            generation = int(parts[4]) if len(parts) == 5 else 0
            if generation < 0:
                raise ValueError
            return UUID(parts[0]), UUID(parts[1]), parts[2], parts[3] == "1", generation
        except (ValueError, IndexError) as exc:
            raise AuthenticationError from exc

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
