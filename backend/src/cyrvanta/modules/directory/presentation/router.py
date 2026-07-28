from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from cyrvanta.modules.directory.application.crypto import SecretCipher
from cyrvanta.modules.directory.application.schemas import (
    DirectoryConfigurationResponse,
    DirectoryConfigurationWrite,
    DirectoryGroupMappingResponse,
    DirectoryGroupMappingsWrite,
    DirectoryTestResponse,
)
from cyrvanta.modules.directory.application.service import (
    DirectoryAdministrationService,
    DirectoryConfigurationConflict,
    DirectoryConfigurationNotFound,
)
from cyrvanta.modules.directory.infrastructure.ldap_provider import LdapDirectoryProvider
from cyrvanta.shared.config import get_settings
from cyrvanta.shared.dependencies import SecurityContext, require_permission

router = APIRouter(prefix="/directory", tags=["directory"])
DirectoryRead = Annotated[SecurityContext, Depends(require_permission("directory.read"))]
DirectoryManage = Annotated[SecurityContext, Depends(require_permission("directory.manage"))]


def get_directory_service() -> DirectoryAdministrationService:
    return DirectoryAdministrationService(
        SecretCipher(get_settings().integration_encryption_key),
        LdapDirectoryProvider(),
    )


Service = Annotated[DirectoryAdministrationService, Depends(get_directory_service)]


def correlation_id(request: Request) -> UUID:
    return UUID(request.state.correlation_id)


def translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, DirectoryConfigurationNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Directory configuration not found")
    return HTTPException(status.HTTP_409_CONFLICT, "Directory configuration is not ready")


@router.get("/configuration", response_model=DirectoryConfigurationResponse)
async def get_configuration(
    context: DirectoryRead, service: Service
) -> DirectoryConfigurationResponse:
    try:
        return await service.get_configuration(context.tenant_id)
    except DirectoryConfigurationNotFound as exc:
        raise translate_error(exc) from exc


@router.put("/configuration", response_model=DirectoryConfigurationResponse)
async def put_configuration(
    payload: DirectoryConfigurationWrite,
    request: Request,
    context: DirectoryManage,
    service: Service,
) -> DirectoryConfigurationResponse:
    try:
        return await service.put_configuration(
            context.tenant_id, context.user_id, payload, correlation_id(request)
        )
    except (DirectoryConfigurationConflict, DirectoryConfigurationNotFound) as exc:
        raise translate_error(exc) from exc


@router.post("/configuration/test", response_model=DirectoryTestResponse)
async def test_configuration(
    request: Request, context: DirectoryManage, service: Service
) -> DirectoryTestResponse:
    try:
        return await service.test_configuration(
            context.tenant_id, context.user_id, correlation_id(request)
        )
    except DirectoryConfigurationNotFound as exc:
        raise translate_error(exc) from exc


@router.post("/configuration/activate", response_model=DirectoryConfigurationResponse)
async def activate_configuration(
    request: Request, context: DirectoryManage, service: Service
) -> DirectoryConfigurationResponse:
    try:
        return await service.set_enabled(
            context.tenant_id, context.user_id, correlation_id(request), True
        )
    except (DirectoryConfigurationConflict, DirectoryConfigurationNotFound) as exc:
        raise translate_error(exc) from exc


@router.post("/configuration/disable", response_model=DirectoryConfigurationResponse)
async def disable_configuration(
    request: Request, context: DirectoryManage, service: Service
) -> DirectoryConfigurationResponse:
    try:
        return await service.set_enabled(
            context.tenant_id, context.user_id, correlation_id(request), False
        )
    except DirectoryConfigurationNotFound as exc:
        raise translate_error(exc) from exc


@router.get("/group-mappings", response_model=list[DirectoryGroupMappingResponse])
async def list_group_mappings(
    context: DirectoryRead, service: Service
) -> list[DirectoryGroupMappingResponse]:
    return await service.list_group_mappings(context.tenant_id)


@router.put("/group-mappings", response_model=list[DirectoryGroupMappingResponse])
async def replace_group_mappings(
    payload: DirectoryGroupMappingsWrite,
    request: Request,
    context: DirectoryManage,
    service: Service,
) -> list[DirectoryGroupMappingResponse]:
    try:
        return await service.replace_group_mappings(
            context.tenant_id,
            context.user_id,
            payload,
            correlation_id(request),
        )
    except DirectoryConfigurationConflict as exc:
        raise translate_error(exc) from exc
