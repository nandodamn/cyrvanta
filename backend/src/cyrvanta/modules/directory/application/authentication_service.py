from datetime import UTC, datetime
from secrets import token_urlsafe
from uuid import UUID

from pwdlib import PasswordHash
from redis.asyncio import Redis
from sqlalchemy import delete, select

from cyrvanta.modules.directory.application.crypto import SecretCipher
from cyrvanta.modules.directory.application.schemas import DirectoryLoginRequest
from cyrvanta.modules.directory.domain.ports import (
    DirectoryAuthenticationRequest,
    DirectoryConnection,
    DirectoryProvider,
)
from cyrvanta.modules.directory.infrastructure.models import (
    DirectoryConfigurationModel,
    DirectoryGroupMappingModel,
    DirectoryIdentityModel,
)
from cyrvanta.modules.identity.application.schemas import TokenResponse
from cyrvanta.modules.identity.application.service import AuthenticationService
from cyrvanta.modules.identity.infrastructure.models import (
    AuditEventModel,
    RoleModel,
    TenantModel,
    UserModel,
    UserRoleModel,
)
from cyrvanta.shared.database import SessionFactory, tenant_session


class DirectoryAuthenticationError(Exception):
    pass


class DirectoryAuthenticationService:
    def __init__(self, redis: Redis, cipher: SecretCipher, provider: DirectoryProvider) -> None:
        self.redis = redis
        self.cipher = cipher
        self.provider = provider

    async def login(self, payload: DirectoryLoginRequest, correlation_id: UUID) -> TokenResponse:
        async with SessionFactory() as session:
            tenant = await session.scalar(
                select(TenantModel).where(
                    TenantModel.slug == payload.tenant_slug,
                    TenantModel.status == "active",
                )
            )
        if tenant is None:
            raise DirectoryAuthenticationError
        async with tenant_session(tenant.id) as session:
            configuration = await session.scalar(
                select(DirectoryConfigurationModel).where(
                    DirectoryConfigurationModel.status == "active"
                )
            )
            if configuration is None:
                raise DirectoryAuthenticationError
            principal = await self.provider.authenticate(
                DirectoryAuthenticationRequest(
                    configuration=DirectoryConnection(
                        server_uri=configuration.server_uri,
                        use_starttls=configuration.use_starttls,
                        bind_dn=configuration.bind_dn,
                        bind_password=self.cipher.decrypt(configuration.bind_secret_ciphertext),
                        base_dn=configuration.base_dn,
                        timeout_seconds=configuration.timeout_seconds,
                        ca_certificate_pem=configuration.ca_certificate_pem,
                    ),
                    base_dn=configuration.base_dn,
                    user_filter=configuration.user_filter,
                    username=payload.username,
                    password=payload.password,
                    subject_attribute=configuration.subject_attribute,
                    email_attribute=configuration.email_attribute,
                    display_name_attribute=configuration.display_name_attribute,
                    group_attribute=configuration.group_attribute,
                )
            )
            if principal is None:
                raise DirectoryAuthenticationError
            identity = await session.scalar(
                select(DirectoryIdentityModel).where(
                    DirectoryIdentityModel.provider_type == configuration.provider_type,
                    DirectoryIdentityModel.external_subject == principal.external_subject,
                )
            )
            jit_created = identity is None
            if identity is None:
                if not configuration.jit_enabled:
                    raise DirectoryAuthenticationError
                existing_email = await session.scalar(
                    select(UserModel.id).where(UserModel.email == principal.email)
                )
                if existing_email is not None:
                    raise DirectoryAuthenticationError
                user = UserModel(
                    tenant_id=tenant.id,
                    email=principal.email,
                    display_name=principal.display_name,
                    password_hash=PasswordHash.recommended().hash(token_urlsafe(48)),
                    is_active=True,
                )
                session.add(user)
                await session.flush()
                identity = DirectoryIdentityModel(
                    tenant_id=tenant.id,
                    user_id=user.id,
                    provider_type=configuration.provider_type,
                    external_subject=principal.external_subject,
                    normalized_username=principal.username.casefold(),
                    last_authenticated_at=datetime.now(UTC),
                )
                session.add(identity)
            else:
                linked_user = await session.get(UserModel, identity.user_id)
                if linked_user is None or not linked_user.is_active:
                    raise DirectoryAuthenticationError
                user = linked_user
                identity.last_authenticated_at = datetime.now(UTC)
            group_names = {item.casefold() for item in principal.groups}
            mapped_roles = (
                await session.scalars(
                    select(RoleModel)
                    .join(
                        DirectoryGroupMappingModel,
                        DirectoryGroupMappingModel.role_id == RoleModel.id,
                    )
                    .where(
                        DirectoryGroupMappingModel.external_group.in_(group_names),
                        RoleModel.code != "tenant-admin",
                    )
                )
            ).all()
            if jit_created and not mapped_roles:
                raise DirectoryAuthenticationError
            await session.execute(
                delete(UserRoleModel).where(
                    UserRoleModel.user_id == user.id,
                    UserRoleModel.assignment_source == "directory",
                )
            )
            manual_role_ids = set(
                (
                    await session.scalars(
                        select(UserRoleModel.role_id).where(
                            UserRoleModel.user_id == user.id,
                            UserRoleModel.assignment_source == "manual",
                        )
                    )
                ).all()
            )
            session.add_all(
                UserRoleModel(
                    tenant_id=tenant.id,
                    user_id=user.id,
                    role_id=role.id,
                    assignment_source="directory",
                )
                for role in mapped_roles
                if role.id not in manual_role_ids
            )
            session.add(
                AuditEventModel(
                    tenant_id=tenant.id,
                    actor_user_id=user.id,
                    action="auth.directory.login",
                    resource_type="session",
                    outcome="success",
                    correlation_id=correlation_id,
                    details={"provider": configuration.provider_type},
                )
            )
        return await AuthenticationService(self.redis).issue_user(user, payload.remember_me)
