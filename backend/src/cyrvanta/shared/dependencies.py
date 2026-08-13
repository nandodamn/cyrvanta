from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import and_, select

from cyrvanta.modules.identity.application.tokens import TokenService
from cyrvanta.modules.identity.infrastructure.models import (
    PermissionModel,
    RolePermissionModel,
    UserModel,
    UserRoleModel,
)
from cyrvanta.shared.database import tenant_session

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class SecurityContext:
    user_id: UUID
    tenant_id: UUID
    email: str


async def get_security_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> SecurityContext:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    claims = TokenService().decode_access_token(credentials.credentials)
    context = SecurityContext(
        user_id=UUID(claims["sub"]),
        tenant_id=UUID(claims["tenant_id"]),
        email=claims["email"],
    )
    async with tenant_session(context.tenant_id) as session:
        active_user = await session.scalar(
            select(UserModel.id).where(
                UserModel.tenant_id == context.tenant_id,
                UserModel.id == context.user_id,
                UserModel.is_active.is_(True),
            )
        )
    if active_user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    return context


def require_permission(
    permission_code: str,
) -> Callable[..., Coroutine[Any, Any, SecurityContext]]:
    async def dependency(
        context: SecurityContext = Depends(get_security_context),
    ) -> SecurityContext:
        await authorize(context, permission_code)
        return context

    return dependency


def require_any_permission(
    *permission_codes: str,
) -> Callable[..., Coroutine[Any, Any, SecurityContext]]:
    if not permission_codes:
        raise ValueError("At least one permission code is required")

    async def dependency(
        context: SecurityContext = Depends(get_security_context),
    ) -> SecurityContext:
        for permission_code in permission_codes:
            if await is_authorized(context, permission_code):
                return context
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Permission denied")

    return dependency


async def authorize(context: SecurityContext, permission_code: str) -> None:
    if not await is_authorized(context, permission_code):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Permission denied")


async def is_authorized(context: SecurityContext, permission_code: str) -> bool:
    async with tenant_session(context.tenant_id) as session:
        granted = await session.scalar(
            select(PermissionModel.id)
            .join(
                RolePermissionModel,
                RolePermissionModel.permission_id == PermissionModel.id,
            )
            .join(
                UserRoleModel,
                and_(
                    UserRoleModel.role_id == RolePermissionModel.role_id,
                    UserRoleModel.tenant_id == RolePermissionModel.tenant_id,
                ),
            )
            .join(
                UserModel,
                and_(
                    UserModel.id == UserRoleModel.user_id,
                    UserModel.tenant_id == UserRoleModel.tenant_id,
                ),
            )
            .where(
                UserRoleModel.tenant_id == context.tenant_id,
                RolePermissionModel.tenant_id == context.tenant_id,
                UserRoleModel.user_id == context.user_id,
                UserModel.is_active.is_(True),
                PermissionModel.code == permission_code,
            )
            .limit(1)
        )
    return granted is not None
