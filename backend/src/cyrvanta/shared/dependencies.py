from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from cyrvanta.modules.identity.application.tokens import TokenService
from cyrvanta.modules.identity.infrastructure.models import (
    PermissionModel,
    RolePermissionModel,
    UserRoleModel,
)
from cyrvanta.shared.database import tenant_session

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class SecurityContext:
    user_id: UUID
    tenant_id: UUID
    email: str


def get_security_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> SecurityContext:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    claims = TokenService().decode_access_token(credentials.credentials)
    return SecurityContext(
        user_id=UUID(claims["sub"]),
        tenant_id=UUID(claims["tenant_id"]),
        email=claims["email"],
    )


def require_permission(
    permission_code: str,
) -> Callable[..., Coroutine[Any, Any, SecurityContext]]:
    async def dependency(
        context: SecurityContext = Depends(get_security_context),
    ) -> SecurityContext:
        await authorize(context, permission_code)
        return context

    return dependency


async def authorize(context: SecurityContext, permission_code: str) -> None:
    async with tenant_session(context.tenant_id) as session:
        granted = await session.scalar(
            select(PermissionModel.id)
            .join(
                RolePermissionModel,
                RolePermissionModel.permission_id == PermissionModel.id,
            )
            .join(UserRoleModel, UserRoleModel.role_id == RolePermissionModel.role_id)
            .where(
                UserRoleModel.user_id == context.user_id,
                PermissionModel.code == permission_code,
            )
            .limit(1)
        )
    if granted is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Permission denied")
