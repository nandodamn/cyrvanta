from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from cyrvanta.modules.identity.application.schemas import (
    AccessTokenResponse,
    CurrentUserResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
)
from cyrvanta.modules.identity.application.service import AuthenticationError, AuthenticationService
from cyrvanta.modules.identity.presentation.session_cookie import (
    clear_refresh_cookie,
    resolve_refresh_token,
    set_refresh_cookie,
)
from cyrvanta.shared.config import get_settings
from cyrvanta.shared.dependencies import (
    SecurityContext,
    get_security_context,
    granted_permissions,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def get_auth_service(request: Request) -> AuthenticationService:
    return AuthenticationService(request.app.state.redis)


def request_correlation_id(request: Request) -> UUID:
    return UUID(request.state.correlation_id)


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    correlation_id: UUID = Depends(request_correlation_id),
    service: AuthenticationService = Depends(get_auth_service),
) -> TokenResponse:
    try:
        tokens = await service.login(payload, correlation_id)
        set_refresh_cookie(response, tokens, get_settings())
        return tokens
    except AuthenticationError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials") from exc


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    service: AuthenticationService = Depends(get_auth_service),
) -> TokenResponse:
    try:
        tokens = await service.refresh(resolve_refresh_token(request, payload))
        set_refresh_cookie(response, tokens, get_settings())
        return tokens
    except AuthenticationError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token") from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    payload: LogoutRequest | None = None,
    service: AuthenticationService = Depends(get_auth_service),
) -> None:
    await service.logout(resolve_refresh_token(request, payload))
    clear_refresh_cookie(response, get_settings())


@router.get("/me/permissions", response_model=list[str])
async def my_permissions(
    context: SecurityContext = Depends(get_security_context),
) -> list[str]:
    """What the signed-in person may attempt, as codes.

    The interface needs this to stop offering what will be refused. Without it
    a screen either shows every control and lets the server say no -- which
    teaches people the product is broken -- or reads a 403 as an empty result,
    which is worse: it reports an absence of data where there is only an
    absence of permission.

    Only ever the caller's own set: it is derived from their security context,
    not from a parameter, so it cannot be asked about anybody else.
    """
    return sorted(await granted_permissions(context))


@router.get("/me", response_model=CurrentUserResponse)
async def me(
    context: SecurityContext = Depends(get_security_context),
    service: AuthenticationService = Depends(get_auth_service),
) -> CurrentUserResponse:
    try:
        return await service.current_user(context.user_id, context.tenant_id)
    except AuthenticationError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User is not active") from exc
