from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from cyrvanta.modules.identity.application.administration_schemas import (
    AuditEventResponse,
    IdentifierList,
    PasswordUpdate,
    PermissionResponse,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    TenantResponse,
    TenantUpdate,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from cyrvanta.modules.identity.application.administration_service import (
    AdministrationService,
    ResourceConflict,
    ResourceNotFound,
)
from cyrvanta.shared.dependencies import SecurityContext, require_permission

router = APIRouter(tags=["administration"])


def get_administration_service(request: Request) -> AdministrationService:
    return AdministrationService(request.app.state.redis)


Service = Annotated[AdministrationService, Depends(get_administration_service)]
TenantRead = Annotated[SecurityContext, Depends(require_permission("tenant.read"))]
TenantManage = Annotated[SecurityContext, Depends(require_permission("tenant.manage"))]
UserRead = Annotated[SecurityContext, Depends(require_permission("user.read"))]
UserManage = Annotated[SecurityContext, Depends(require_permission("user.manage"))]
RoleRead = Annotated[SecurityContext, Depends(require_permission("role.read"))]
RoleManage = Annotated[SecurityContext, Depends(require_permission("role.manage"))]
AuditRead = Annotated[SecurityContext, Depends(require_permission("audit.read"))]


def correlation_id(request: Request) -> UUID:
    return UUID(request.state.correlation_id)


def translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ResourceNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found")
    return HTTPException(status.HTTP_409_CONFLICT, "Operation conflicts with current state")


@router.get("/tenant", response_model=TenantResponse)
async def get_tenant(context: TenantRead, service: Service) -> TenantResponse:
    return TenantResponse.model_validate(await service.get_tenant(context.tenant_id))


@router.patch("/tenant", response_model=TenantResponse)
async def update_tenant(
    payload: TenantUpdate, request: Request, context: TenantManage, service: Service
) -> TenantResponse:
    tenant = await service.update_tenant(
        context.tenant_id, context.user_id, payload, correlation_id(request)
    )
    return TenantResponse.model_validate(tenant)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    context: UserRead,
    service: Service,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> list[UserResponse]:
    return [
        UserResponse.model_validate(item)
        for item in await service.list_users(context.tenant_id, limit, offset, q)
    ]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate, request: Request, context: UserManage, service: Service
) -> UserResponse:
    try:
        user = await service.create_user(
            context.tenant_id, context.user_id, payload, correlation_id(request)
        )
    except (ResourceConflict, ResourceNotFound) as exc:
        raise translate_error(exc) from exc
    return UserResponse.model_validate(user)


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, context: UserRead, service: Service) -> UserResponse:
    try:
        return UserResponse.model_validate(await service.get_user(context.tenant_id, user_id))
    except ResourceNotFound as exc:
        raise translate_error(exc) from exc


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    request: Request,
    context: UserManage,
    service: Service,
) -> UserResponse:
    try:
        user = await service.update_user(
            context.tenant_id, context.user_id, user_id, payload, correlation_id(request)
        )
    except (ResourceConflict, ResourceNotFound) as exc:
        raise translate_error(exc) from exc
    return UserResponse.model_validate(user)


@router.post("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def update_password(
    user_id: UUID,
    payload: PasswordUpdate,
    request: Request,
    context: UserManage,
    service: Service,
) -> None:
    try:
        await service.update_password(
            context.tenant_id, context.user_id, user_id, payload, correlation_id(request)
        )
    except ResourceNotFound as exc:
        raise translate_error(exc) from exc


@router.put("/users/{user_id}/roles", status_code=status.HTTP_204_NO_CONTENT)
async def replace_user_roles(
    user_id: UUID,
    payload: IdentifierList,
    request: Request,
    context: UserManage,
    service: Service,
) -> None:
    try:
        await service.replace_user_roles(
            context.tenant_id, context.user_id, user_id, payload, correlation_id(request)
        )
    except (ResourceConflict, ResourceNotFound) as exc:
        raise translate_error(exc) from exc


@router.get("/users/{user_id}/roles", response_model=list[UUID])
async def list_user_roles(user_id: UUID, context: UserRead, service: Service) -> list[UUID]:
    try:
        return await service.list_user_roles(context.tenant_id, user_id)
    except ResourceNotFound as exc:
        raise translate_error(exc) from exc


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(context: RoleRead, service: Service) -> list[RoleResponse]:
    return [
        RoleResponse.model_validate(item) for item in await service.list_roles(context.tenant_id)
    ]


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreate, request: Request, context: RoleManage, service: Service
) -> RoleResponse:
    try:
        role = await service.create_role(
            context.tenant_id, context.user_id, payload, correlation_id(request)
        )
    except (ResourceConflict, ResourceNotFound) as exc:
        raise translate_error(exc) from exc
    return RoleResponse.model_validate(role)


@router.get("/roles/{role_id}", response_model=RoleResponse)
async def get_role(role_id: UUID, context: RoleRead, service: Service) -> RoleResponse:
    try:
        return RoleResponse.model_validate(await service.get_role(context.tenant_id, role_id))
    except ResourceNotFound as exc:
        raise translate_error(exc) from exc


@router.patch("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: UUID,
    payload: RoleUpdate,
    request: Request,
    context: RoleManage,
    service: Service,
) -> RoleResponse:
    try:
        role = await service.update_role(
            context.tenant_id, context.user_id, role_id, payload, correlation_id(request)
        )
    except (ResourceConflict, ResourceNotFound) as exc:
        raise translate_error(exc) from exc
    return RoleResponse.model_validate(role)


@router.put("/roles/{role_id}/permissions", status_code=status.HTTP_204_NO_CONTENT)
async def replace_role_permissions(
    role_id: UUID,
    payload: IdentifierList,
    request: Request,
    context: RoleManage,
    service: Service,
) -> None:
    try:
        await service.replace_role_permissions(
            context.tenant_id, context.user_id, role_id, payload, correlation_id(request)
        )
    except (ResourceConflict, ResourceNotFound) as exc:
        raise translate_error(exc) from exc


@router.get("/roles/{role_id}/permissions", response_model=list[UUID])
async def list_role_permissions(role_id: UUID, context: RoleRead, service: Service) -> list[UUID]:
    try:
        return await service.list_role_permissions(context.tenant_id, role_id)
    except ResourceNotFound as exc:
        raise translate_error(exc) from exc


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(context: RoleRead, service: Service) -> list[PermissionResponse]:
    return [
        PermissionResponse.model_validate(item)
        for item in await service.list_permissions(context.tenant_id)
    ]


@router.get("/audit-events", response_model=list[AuditEventResponse])
async def list_audit_events(
    context: AuditRead,
    service: Service,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> list[AuditEventResponse]:
    return [
        AuditEventResponse.model_validate(item)
        for item in await service.list_audit(context.tenant_id, limit, offset, q)
    ]
