from uuid import uuid4

from cyrvanta.modules.identity.application.tokens import TokenService


def test_access_token_preserves_tenant_context() -> None:
    service = TokenService()
    user_id, tenant_id = uuid4(), uuid4()
    token = service.create_access_token(user_id, tenant_id, "analyst@example.test")
    claims = service.decode_access_token(token)
    assert claims["sub"] == str(user_id)
    assert claims["tenant_id"] == str(tenant_id)


def test_refresh_token_is_stored_by_digest() -> None:
    token = TokenService.new_refresh_token()
    digest = TokenService.refresh_digest(token)
    assert token not in digest
    assert len(digest) == 64
