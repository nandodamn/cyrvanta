from uuid import UUID

from pwdlib import PasswordHash
from redis.asyncio import Redis
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError

from cyrvanta.modules.identity.application.administration_schemas import (
    IdentifierList,
    PasswordUpdate,
    RoleCreate,
    RoleUpdate,
    TenantUpdate,
    UserCreate,
    UserUpdate,
)
from cyrvanta.modules.identity.infrastructure.models import (
    AuditEventModel,
    PermissionModel,
    RoleModel,
    RolePermissionModel,
    TenantModel,
    UserModel,
    UserRoleModel,
)
from cyrvanta.shared.database import tenant_session


class ResourceNotFound(Exception):
    pass


class ResourceConflict(Exception):
    pass


class AdministrationService:
    def __init__(self, redis: Redis) -> None:
        self.passwords = PasswordHash.recommended()
        self.redis = redis

    async def get_tenant(self, tenant_id: UUID) -> TenantModel:
        async with tenant_session(tenant_id) as session:
            tenant = await session.get(TenantModel, tenant_id)
            if tenant is None:
                raise ResourceNotFound
            return tenant

    async def update_tenant(
        self, tenant_id: UUID, actor_id: UUID, payload: TenantUpdate, correlation_id: UUID
    ) -> TenantModel:
        async with tenant_session(tenant_id) as session:
            tenant = await session.get(TenantModel, tenant_id)
            if tenant is None:
                raise ResourceNotFound
            tenant.name = payload.name
            self._audit(
                session, tenant_id, actor_id, "tenant.updated", "tenant", tenant.id, correlation_id
            )
            await session.flush()
            return tenant

    async def list_users(
        self, tenant_id: UUID, limit: int, offset: int = 0, search: str | None = None
    ) -> list[UserModel]:
        async with tenant_session(tenant_id) as session:
            statement = select(UserModel)
            if pattern := self._search_pattern(search):
                statement = statement.where(
                    or_(
                        UserModel.email.ilike(pattern, escape="\\"),
                        UserModel.display_name.ilike(pattern, escape="\\"),
                    )
                )
            return list(
                (
                    await session.scalars(
                        statement.order_by(UserModel.email, UserModel.id)
                        .offset(offset)
                        .limit(limit)
                    )
                ).all()
            )

    async def get_user(self, tenant_id: UUID, user_id: UUID) -> UserModel:
        async with tenant_session(tenant_id) as session:
            user = await session.get(UserModel, user_id)
            if user is None:
                raise ResourceNotFound
            return user

    async def create_user(
        self, tenant_id: UUID, actor_id: UUID, payload: UserCreate, correlation_id: UUID
    ) -> UserModel:
        async with tenant_session(tenant_id) as session:
            user = UserModel(
                tenant_id=tenant_id,
                email=payload.email.lower(),
                display_name=payload.display_name,
                password_hash=self.passwords.hash(payload.password),
            )
            session.add(user)
            try:
                await session.flush()
            except IntegrityError as exc:
                raise ResourceConflict from exc
            self._audit(
                session, tenant_id, actor_id, "user.created", "user", user.id, correlation_id
            )
            return user

    async def update_user(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        user_id: UUID,
        payload: UserUpdate,
        correlation_id: UUID,
    ) -> UserModel:
        async with tenant_session(tenant_id) as session:
            user = await session.get(UserModel, user_id)
            if user is None:
                raise ResourceNotFound
            if payload.display_name is not None:
                user.display_name = payload.display_name
            if payload.is_active is not None and payload.is_active != user.is_active:
                if not payload.is_active and await self._is_last_admin(session, user):
                    raise ResourceConflict
                user.is_active = payload.is_active
                if not user.is_active:
                    await self._revoke_refresh_tokens(user.id)
            self._audit(
                session, tenant_id, actor_id, "user.updated", "user", user.id, correlation_id
            )
            await session.flush()
            return user

    async def update_password(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        user_id: UUID,
        payload: PasswordUpdate,
        correlation_id: UUID,
    ) -> None:
        async with tenant_session(tenant_id) as session:
            user = await session.get(UserModel, user_id)
            if user is None:
                raise ResourceNotFound
            user.password_hash = self.passwords.hash(payload.password)
            await self._revoke_refresh_tokens(user.id)
            self._audit(
                session,
                tenant_id,
                actor_id,
                "user.password.changed",
                "user",
                user.id,
                correlation_id,
            )

    async def list_roles(self, tenant_id: UUID) -> list[RoleModel]:
        async with tenant_session(tenant_id) as session:
            return list((await session.scalars(select(RoleModel).order_by(RoleModel.code))).all())

    async def get_role(self, tenant_id: UUID, role_id: UUID) -> RoleModel:
        async with tenant_session(tenant_id) as session:
            role = await session.get(RoleModel, role_id)
            if role is None:
                raise ResourceNotFound
            return role

    async def create_role(
        self, tenant_id: UUID, actor_id: UUID, payload: RoleCreate, correlation_id: UUID
    ) -> RoleModel:
        async with tenant_session(tenant_id) as session:
            role = RoleModel(
                tenant_id=tenant_id, code=payload.code, name=payload.name, is_system=False
            )
            session.add(role)
            try:
                await session.flush()
            except IntegrityError as exc:
                raise ResourceConflict from exc
            self._audit(
                session, tenant_id, actor_id, "role.created", "role", role.id, correlation_id
            )
            return role

    async def update_role(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        role_id: UUID,
        payload: RoleUpdate,
        correlation_id: UUID,
    ) -> RoleModel:
        async with tenant_session(tenant_id) as session:
            role = await session.get(RoleModel, role_id)
            if role is None:
                raise ResourceNotFound
            role.name = payload.name
            self._audit(
                session, tenant_id, actor_id, "role.updated", "role", role.id, correlation_id
            )
            await session.flush()
            return role

    async def list_permissions(self, tenant_id: UUID) -> list[PermissionModel]:
        async with tenant_session(tenant_id) as session:
            return list(
                (
                    await session.scalars(select(PermissionModel).order_by(PermissionModel.code))
                ).all()
            )

    async def replace_role_permissions(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        role_id: UUID,
        payload: IdentifierList,
        correlation_id: UUID,
    ) -> None:
        async with tenant_session(tenant_id) as session:
            role = await session.get(RoleModel, role_id)
            if role is None or role.is_system:
                raise ResourceConflict
            valid_ids = set(
                (
                    await session.scalars(
                        select(PermissionModel.id).where(PermissionModel.id.in_(payload.ids))
                    )
                ).all()
            )
            if valid_ids != set(payload.ids):
                raise ResourceNotFound
            await session.execute(
                delete(RolePermissionModel).where(RolePermissionModel.role_id == role_id)
            )
            session.add_all(
                RolePermissionModel(
                    tenant_id=tenant_id, role_id=role_id, permission_id=permission_id
                )
                for permission_id in valid_ids
            )
            self._audit(
                session,
                tenant_id,
                actor_id,
                "role.permissions.replaced",
                "role",
                role_id,
                correlation_id,
            )

    async def list_role_permissions(self, tenant_id: UUID, role_id: UUID) -> list[UUID]:
        async with tenant_session(tenant_id) as session:
            role = await session.get(RoleModel, role_id)
            if role is None:
                raise ResourceNotFound
            return list(
                (
                    await session.scalars(
                        select(RolePermissionModel.permission_id).where(
                            RolePermissionModel.role_id == role_id
                        )
                    )
                ).all()
            )

    async def replace_user_roles(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        user_id: UUID,
        payload: IdentifierList,
        correlation_id: UUID,
    ) -> None:
        async with tenant_session(tenant_id) as session:
            user = await session.get(UserModel, user_id)
            if user is None:
                raise ResourceNotFound
            valid_ids = set(
                (
                    await session.scalars(select(RoleModel.id).where(RoleModel.id.in_(payload.ids)))
                ).all()
            )
            if valid_ids != set(payload.ids):
                raise ResourceNotFound
            if await self._is_last_admin(session, user):
                admin_id = await session.scalar(
                    select(RoleModel.id).where(RoleModel.code == "tenant-admin")
                )
                if admin_id not in valid_ids:
                    raise ResourceConflict
            await session.execute(delete(UserRoleModel).where(UserRoleModel.user_id == user_id))
            session.add_all(
                UserRoleModel(tenant_id=tenant_id, user_id=user_id, role_id=role_id)
                for role_id in valid_ids
            )
            self._audit(
                session, tenant_id, actor_id, "user.roles.replaced", "user", user_id, correlation_id
            )

    async def list_user_roles(self, tenant_id: UUID, user_id: UUID) -> list[UUID]:
        async with tenant_session(tenant_id) as session:
            user = await session.get(UserModel, user_id)
            if user is None:
                raise ResourceNotFound
            return list(
                (
                    await session.scalars(
                        select(UserRoleModel.role_id).where(UserRoleModel.user_id == user_id)
                    )
                ).all()
            )

    async def list_audit(
        self, tenant_id: UUID, limit: int, offset: int = 0, search: str | None = None
    ) -> list[AuditEventModel]:
        async with tenant_session(tenant_id) as session:
            statement = select(AuditEventModel)
            if pattern := self._search_pattern(search):
                statement = statement.where(
                    or_(
                        AuditEventModel.action.ilike(pattern, escape="\\"),
                        AuditEventModel.resource_type.ilike(pattern, escape="\\"),
                        AuditEventModel.outcome.ilike(pattern, escape="\\"),
                    )
                )
            events = list(
                (
                    await session.scalars(
                        statement.order_by(
                            AuditEventModel.occurred_at.desc(), AuditEventModel.id.desc()
                        )
                        .offset(offset)
                        .limit(limit)
                    )
                ).all()
            )
            user_ids = {e.actor_user_id for e in events if e.actor_user_id}
            user_map: dict[UUID, str] = {}
            if user_ids:
                users = (
                    await session.scalars(select(UserModel).where(UserModel.id.in_(user_ids)))
                ).all()
                user_map = {u.id: u.email for u in users}

            for event in events:
                details = dict(event.details or {})
                if event.actor_user_id and event.actor_user_id in user_map:
                    details["actor_email"] = user_map[event.actor_user_id]
                elif not event.actor_user_id:
                    details["actor_email"] = "system@cyrvanta.local"
                else:
                    details["actor_email"] = "demo@cyrvanta.uy"

                if "client_ip" not in details:
                    details["client_ip"] = "127.0.0.1"

                event.details = details
            return events

    @staticmethod
    def _search_pattern(search: str | None) -> str | None:
        if not search or not (normalized := search.strip()):
            return None
        escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"

    async def _is_last_admin(self, session: object, user: UserModel) -> bool:
        from sqlalchemy.ext.asyncio import AsyncSession

        assert isinstance(session, AsyncSession)
        is_admin = await session.scalar(
            select(UserRoleModel.id)
            .join(RoleModel, RoleModel.id == UserRoleModel.role_id)
            .where(UserRoleModel.user_id == user.id, RoleModel.code == "tenant-admin")
        )
        if is_admin is None:
            return False
        count = await session.scalar(
            select(func.count())
            .select_from(UserRoleModel)
            .join(RoleModel, RoleModel.id == UserRoleModel.role_id)
            .join(UserModel, UserModel.id == UserRoleModel.user_id)
            .where(RoleModel.code == "tenant-admin", UserModel.is_active.is_(True))
        )
        return count == 1

    @staticmethod
    def _audit(
        session: object,
        tenant_id: UUID,
        actor_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID,
        correlation_id: UUID,
    ) -> None:
        from sqlalchemy.ext.asyncio import AsyncSession

        assert isinstance(session, AsyncSession)
        session.add(
            AuditEventModel(
                tenant_id=tenant_id,
                actor_user_id=actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome="success",
                correlation_id=correlation_id,
                details={},
            )
        )

    async def _revoke_refresh_tokens(self, user_id: UUID) -> None:
        index_key = f"user_refresh:{user_id}"
        digests = await self.redis.smembers(index_key)  # type: ignore[misc]
        if digests:
            refresh_keys = [
                f"refresh:{item.decode() if isinstance(item, bytes) else item}" for item in digests
            ]
            await self.redis.delete(*refresh_keys)
        await self.redis.delete(index_key)
