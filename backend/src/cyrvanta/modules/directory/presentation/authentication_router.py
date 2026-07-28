from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from cyrvanta.modules.directory.application.authentication_service import (
    DirectoryAuthenticationError,
    DirectoryAuthenticationService,
)
from cyrvanta.modules.directory.application.crypto import SecretCipher
from cyrvanta.modules.directory.application.schemas import DirectoryLoginRequest
from cyrvanta.modules.directory.infrastructure.ldap_provider import LdapDirectoryProvider
from cyrvanta.modules.directory.infrastructure.simulated_provider import SimulatedDirectoryProvider
from cyrvanta.modules.identity.application.schemas import AccessTokenResponse, TokenResponse
from cyrvanta.modules.identity.presentation.session_cookie import set_refresh_cookie
from cyrvanta.shared.config import get_settings

router = APIRouter(prefix="/auth/directory", tags=["authentication"])


def get_service(request: Request) -> DirectoryAuthenticationService:
    settings = get_settings()
    provider = (
        SimulatedDirectoryProvider() if settings.directory_demo_enabled else LdapDirectoryProvider()
    )
    return DirectoryAuthenticationService(
        request.app.state.redis,
        SecretCipher(settings.integration_encryption_key),
        provider,
    )


Service = Annotated[DirectoryAuthenticationService, Depends(get_service)]


@router.post("/login", response_model=AccessTokenResponse)
async def directory_login(
    payload: DirectoryLoginRequest, request: Request, response: Response, service: Service
) -> TokenResponse:
    try:
        tokens = await service.login(payload, UUID(request.state.correlation_id))
        set_refresh_cookie(response, tokens, get_settings())
        return tokens
    except DirectoryAuthenticationError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid directory credentials") from exc
