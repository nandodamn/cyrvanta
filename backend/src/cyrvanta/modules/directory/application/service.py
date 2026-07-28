from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from cyrvanta.modules.directory.application.crypto import SecretCipher
from cyrvanta.modules.directory.application.schemas import (
    DirectoryConfigurationResponse,
    DirectoryConfigurationWrite,
    DirectoryGroupMappingResponse,
    DirectoryGroupMappingsWrite,
    DirectoryLinkWrite,
    DirectoryTestResponse,
)
from cyrvanta.modules.directory.domain.ports import DirectoryConnection, DirectoryProvider
from cyrvanta.modules.directory.infrastructure.models import (
    DirectoryConfigurationModel,
    DirectoryGroupMappingModel,
    DirectoryIdentityModel,
)
from cyrvanta.modules.identity.infrastructure.models import AuditEventModel, RoleModel, UserModel
from cyrvanta.shared.database import tenant_session


class DirectoryConfigurationNotFound(Exception):
    pass


class DirectoryConfigurationConflict(Exception):
    pass


class DirectoryAdministrationService:
    def __init__(self, cipher: SecretCipher, provider: DirectoryProvider) -> None:
        self.cipher = cipher
        self.provider = provider

    async def get_configuration(self, tenant_id: UUID) -> DirectoryConfigurationResponse:
        async with tenant_session(tenant_id) as session:
            configuration = await self._get(session, tenant_id)
            return self._response(configuration)

    async def put_configuration(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        payload: DirectoryConfigurationWrite,
        correlation_id: UUID,
    ) -> DirectoryConfigurationResponse:
        async with tenant_session(tenant_id) as session:
            configuration = await session.scalar(
                select(DirectoryConfigurationModel).where(
                    DirectoryConfigurationModel.tenant_id == tenant_id
                )
            )
            if configuration is None:
                if payload.bind_password is None:
                    raise DirectoryConfigurationConflict
                configuration = DirectoryConfigurationModel(
                    tenant_id=tenant_id,
                    bind_secret_ciphertext=self.cipher.encrypt(payload.bind_password),
                    status="draft",
                )
                session.add(configuration)
            elif payload.bind_password is not None:
                configuration.bind_secret_ciphertext = self.cipher.encrypt(payload.bind_password)
            for field in (
                "provider_type",
                "server_uri",
                "use_starttls",
                "base_dn",
                "bind_dn",
                "user_filter",
                "login_attribute",
                "subject_attribute",
                "email_attribute",
                "display_name_attribute",
                "group_base_dn",
                "group_filter",
                "group_attribute",
                "ca_certificate_pem",
                "jit_enabled",
                "timeout_seconds",
            ):
                setattr(configuration, field, getattr(payload, field))
            configuration.status = "draft"
            await session.flush()
            self._audit(
                session,
                tenant_id,
                actor_id,
                "directory.configuration.saved",
                configuration.id,
                correlation_id,
            )
            return self._response(configuration)

    async def test_configuration(
        self, tenant_id: UUID, actor_id: UUID, correlation_id: UUID
    ) -> DirectoryTestResponse:
        async with tenant_session(tenant_id) as session:
            configuration = await self._get(session, tenant_id)
            result = await self.provider.test_connection(
                DirectoryConnection(
                    server_uri=configuration.server_uri,
                    use_starttls=configuration.use_starttls,
                    bind_dn=configuration.bind_dn,
                    bind_password=self.cipher.decrypt(configuration.bind_secret_ciphertext),
                    base_dn=configuration.base_dn,
                    timeout_seconds=configuration.timeout_seconds,
                    ca_certificate_pem=configuration.ca_certificate_pem,
                )
            )
            configuration.last_tested_at = datetime.now(UTC)
            configuration.last_test_success = result.success
            if not result.success and configuration.status == "active":
                configuration.status = "degraded"
            self._audit(
                session,
                tenant_id,
                actor_id,
                "directory.configuration.tested",
                configuration.id,
                correlation_id,
                outcome="success" if result.success else "failure",
            )
            return DirectoryTestResponse(success=result.success, detail_code=result.detail_code)

    async def set_enabled(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        correlation_id: UUID,
        enabled: bool,
    ) -> DirectoryConfigurationResponse:
        async with tenant_session(tenant_id) as session:
            configuration = await self._get(session, tenant_id)
            if enabled and configuration.last_test_success is not True:
                raise DirectoryConfigurationConflict
            configuration.status = "active" if enabled else "disabled"
            self._audit(
                session,
                tenant_id,
                actor_id,
                "directory.configuration.activated"
                if enabled
                else "directory.configuration.disabled",
                configuration.id,
                correlation_id,
            )
            await session.flush()
            return self._response(configuration)

    async def link_identity(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        user_id: UUID,
        payload: DirectoryLinkWrite,
        correlation_id: UUID,
    ) -> None:
        async with tenant_session(tenant_id) as session:
            user = await session.get(UserModel, user_id)
            configuration = await session.scalar(select(DirectoryConfigurationModel))
            if user is None or configuration is None:
                raise DirectoryConfigurationNotFound
            existing = await session.scalar(
                select(DirectoryIdentityModel).where(
                    DirectoryIdentityModel.provider_type == configuration.provider_type,
                    DirectoryIdentityModel.external_subject == payload.external_subject,
                )
            )
            if existing is not None and existing.user_id != user_id:
                raise DirectoryConfigurationConflict
            if existing is None:
                session.add(
                    DirectoryIdentityModel(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        provider_type=configuration.provider_type,
                        external_subject=payload.external_subject,
                        normalized_username=payload.normalized_username.lower(),
                    )
                )
            self._audit(
                session,
                tenant_id,
                actor_id,
                "directory.identity.linked",
                user_id,
                correlation_id,
            )

    async def unlink_identity(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        user_id: UUID,
        correlation_id: UUID,
    ) -> None:
        async with tenant_session(tenant_id) as session:
            identity = await session.scalar(
                select(DirectoryIdentityModel).where(DirectoryIdentityModel.user_id == user_id)
            )
            if identity is None:
                raise DirectoryConfigurationNotFound
            await session.delete(identity)
            self._audit(
                session,
                tenant_id,
                actor_id,
                "directory.identity.unlinked",
                user_id,
                correlation_id,
            )

    async def list_group_mappings(self, tenant_id: UUID) -> list[DirectoryGroupMappingResponse]:
        async with tenant_session(tenant_id) as session:
            mappings = (
                await session.scalars(
                    select(DirectoryGroupMappingModel).order_by(
                        DirectoryGroupMappingModel.external_group
                    )
                )
            ).all()
            return [
                DirectoryGroupMappingResponse(
                    id=item.id,
                    external_group=item.external_group,
                    role_id=item.role_id,
                )
                for item in mappings
            ]

    async def replace_group_mappings(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        payload: DirectoryGroupMappingsWrite,
        correlation_id: UUID,
    ) -> list[DirectoryGroupMappingResponse]:
        async with tenant_session(tenant_id) as session:
            role_ids = {item.role_id for item in payload.mappings}
            roles = (
                await session.scalars(select(RoleModel).where(RoleModel.id.in_(role_ids)))
            ).all()
            if {role.id for role in roles} != role_ids or any(
                role.code == "tenant-admin" for role in roles
            ):
                raise DirectoryConfigurationConflict
            await session.execute(delete(DirectoryGroupMappingModel))
            created = [
                DirectoryGroupMappingModel(
                    tenant_id=tenant_id,
                    external_group=item.external_group.casefold(),
                    role_id=item.role_id,
                )
                for item in payload.mappings
            ]
            session.add_all(created)
            await session.flush()
            configuration = await session.scalar(select(DirectoryConfigurationModel))
            self._audit(
                session,
                tenant_id,
                actor_id,
                "directory.group_mappings.replaced",
                configuration.id if configuration is not None else tenant_id,
                correlation_id,
            )
            return [
                DirectoryGroupMappingResponse(
                    id=item.id,
                    external_group=item.external_group,
                    role_id=item.role_id,
                )
                for item in created
            ]

    @staticmethod
    async def _get(session: AsyncSession, tenant_id: UUID) -> DirectoryConfigurationModel:
        configuration = await session.scalar(
            select(DirectoryConfigurationModel).where(
                DirectoryConfigurationModel.tenant_id == tenant_id
            )
        )
        if configuration is None:
            raise DirectoryConfigurationNotFound
        return configuration

    @staticmethod
    def _response(
        configuration: DirectoryConfigurationModel,
    ) -> DirectoryConfigurationResponse:
        return DirectoryConfigurationResponse(
            id=configuration.id,
            provider_type=configuration.provider_type,
            status=configuration.status,
            server_uri=configuration.server_uri,
            use_starttls=configuration.use_starttls,
            base_dn=configuration.base_dn,
            bind_dn=configuration.bind_dn,
            has_bind_secret=bool(configuration.bind_secret_ciphertext),
            user_filter=configuration.user_filter,
            login_attribute=configuration.login_attribute,
            subject_attribute=configuration.subject_attribute,
            email_attribute=configuration.email_attribute,
            display_name_attribute=configuration.display_name_attribute,
            group_base_dn=configuration.group_base_dn,
            group_filter=configuration.group_filter,
            group_attribute=configuration.group_attribute,
            has_ca_certificate=bool(configuration.ca_certificate_pem),
            jit_enabled=configuration.jit_enabled,
            timeout_seconds=configuration.timeout_seconds,
            last_test_success=configuration.last_test_success,
        )

    @staticmethod
    def _audit(
        session: AsyncSession,
        tenant_id: UUID,
        actor_id: UUID,
        action: str,
        resource_id: UUID,
        correlation_id: UUID,
        outcome: str = "success",
    ) -> None:
        session.add(
            AuditEventModel(
                tenant_id=tenant_id,
                actor_user_id=actor_id,
                action=action,
                resource_type="directory_configuration",
                resource_id=resource_id,
                outcome=outcome,
                correlation_id=correlation_id,
                details={},
            )
        )
