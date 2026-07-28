from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from cyrvanta.modules.directory.application.schemas import DirectoryLinkWrite
from cyrvanta.modules.directory.application.service import (
    DirectoryAdministrationService,
    DirectoryConfigurationConflict,
    DirectoryConfigurationNotFound,
)
from cyrvanta.modules.directory.presentation.router import get_directory_service
from cyrvanta.shared.dependencies import SecurityContext, require_permission

router = APIRouter(prefix="/users", tags=["directory"])
Service = Annotated[DirectoryAdministrationService, Depends(get_directory_service)]
UserManage = Annotated[SecurityContext, Depends(require_permission("user.manage"))]


@router.post("/{user_id}/directory-link", status_code=status.HTTP_204_NO_CONTENT)
async def link_identity(
    user_id: UUID,
    payload: DirectoryLinkWrite,
    request: Request,
    context: UserManage,
    service: Service,
) -> None:
    try:
        await service.link_identity(
            context.tenant_id,
            context.user_id,
            user_id,
            payload,
            UUID(request.state.correlation_id),
        )
    except DirectoryConfigurationNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found") from exc
    except DirectoryConfigurationConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Identity already linked") from exc


@router.delete("/{user_id}/directory-link", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_identity(
    user_id: UUID, request: Request, context: UserManage, service: Service
) -> None:
    try:
        await service.unlink_identity(
            context.tenant_id,
            context.user_id,
            user_id,
            UUID(request.state.correlation_id),
        )
    except DirectoryConfigurationNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found") from exc
