from fastapi import HTTPException, Request, Response, status

from cyrvanta.modules.identity.application.schemas import RefreshRequest, TokenResponse
from cyrvanta.shared.config import Settings

REFRESH_COOKIE_NAME = "cyrvanta_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"
CSRF_HEADER_NAME = "X-CSRF-Guard"
CSRF_HEADER_VALUE = "1"


def resolve_refresh_token(request: Request, payload: RefreshRequest | None) -> str:
    cookie_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if cookie_token is not None:
        if request.headers.get(CSRF_HEADER_NAME) != CSRF_HEADER_VALUE:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF guard required")
        return cookie_token
    if payload is not None:
        return payload.refresh_token
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh session not found")


def set_refresh_cookie(response: Response, tokens: TokenResponse, settings: Settings) -> None:
    max_age = settings.refresh_token_ttl_days * 24 * 60 * 60 if tokens.remember_me else None
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=tokens.refresh_token,
        max_age=max_age,
        path=REFRESH_COOKIE_PATH,
        secure=settings.secure_session_cookie,
        httponly=True,
        samesite="strict",
    )


def clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        secure=settings.secure_session_cookie,
        httponly=True,
        samesite="strict",
    )
