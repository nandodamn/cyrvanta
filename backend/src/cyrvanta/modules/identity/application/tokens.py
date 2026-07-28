import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from fastapi import HTTPException, status

from cyrvanta.shared.config import get_settings


class TokenService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def create_access_token(self, user_id: UUID, tenant_id: UUID, email: str) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "email": email,
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=self.settings.access_token_ttl_minutes),
        }
        return jwt.encode(payload, self.settings.jwt_secret, algorithm=self.settings.jwt_algorithm)

    def decode_access_token(self, token: str) -> dict[str, Any]:
        try:
            claims: dict[str, Any] = jwt.decode(
                token, self.settings.jwt_secret, algorithms=[self.settings.jwt_algorithm]
            )
            if claims.get("type") != "access":
                raise ValueError("Wrong token type")
            return claims
        except (jwt.PyJWTError, ValueError) as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid access token") from exc

    @staticmethod
    def new_refresh_token() -> str:
        return secrets.token_urlsafe(48)

    @staticmethod
    def refresh_digest(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
