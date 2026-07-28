from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request, Response

from cyrvanta.modules.identity.application.schemas import RefreshRequest, TokenResponse
from cyrvanta.modules.identity.presentation.session_cookie import (
    REFRESH_COOKIE_NAME,
    clear_refresh_cookie,
    resolve_refresh_token,
    set_refresh_cookie,
)


def request_with(headers: list[tuple[bytes, bytes]]) -> Request:
    return Request({"type": "http", "headers": headers})


def cookie_settings() -> SimpleNamespace:
    return SimpleNamespace(refresh_token_ttl_days=7, secure_session_cookie=True)


def test_persistent_cookie_is_http_only_strict_and_scoped() -> None:
    response = Response()
    set_refresh_cookie(
        response,
        TokenResponse(
            access_token="access",  # noqa: S106 - synthetic test value
            refresh_token="r" * 48,
            remember_me=True,
        ),
        cookie_settings(),  # type: ignore[arg-type]
    )
    cookie = response.headers["set-cookie"]
    assert f"{REFRESH_COOKIE_NAME}=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Secure" in cookie
    assert "Path=/api/v1/auth" in cookie
    assert "Max-Age=604800" in cookie


def test_session_cookie_has_no_persistent_max_age() -> None:
    response = Response()
    set_refresh_cookie(
        response,
        TokenResponse(
            access_token="access",  # noqa: S106 - synthetic test value
            refresh_token="r" * 48,
        ),
        cookie_settings(),  # type: ignore[arg-type]
    )
    assert "Max-Age" not in response.headers["set-cookie"]


def test_cookie_refresh_requires_csrf_guard() -> None:
    request = request_with([(b"cookie", f"{REFRESH_COOKIE_NAME}={'r' * 48}".encode())])
    with pytest.raises(HTTPException) as error:
        resolve_refresh_token(request, None)
    assert error.value.status_code == 403


def test_non_browser_refresh_body_remains_supported() -> None:
    request = request_with([])
    token = "r" * 48
    assert resolve_refresh_token(request, RefreshRequest(refresh_token=token)) == token


def test_logout_cookie_uses_matching_security_attributes() -> None:
    response = Response()
    clear_refresh_cookie(response, cookie_settings())  # type: ignore[arg-type]
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Secure" in cookie
    assert "Path=/api/v1/auth" in cookie
