import argparse
import asyncio
from uuid import uuid4

from sqlalchemy import text

from cyrvanta.modules.directory.application.crypto import SecretCipher
from cyrvanta.shared.config import get_settings
from cyrvanta.shared.database import SessionFactory


async def bootstrap(tenant_slug: str) -> None:
    settings = get_settings()
    if settings.environment == "production" or not settings.directory_demo_enabled:
        raise RuntimeError("Directory simulation must be explicitly enabled outside production")
    cipher = SecretCipher(settings.integration_encryption_key)
    async with SessionFactory() as session, session.begin():
        await session.execute(text("SELECT set_config('app.auth_lookup', 'true', true)"))
        tenant_id = await session.scalar(
            text("SELECT id FROM tenants WHERE slug = :slug"), {"slug": tenant_slug}
        )
        if tenant_id is None:
            raise RuntimeError("Tenant not found")
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
            {"tenant": str(tenant_id)},
        )
        await session.execute(
            text("""
                INSERT INTO directory_configurations (
                    id, tenant_id, provider_type, status, server_uri, use_starttls,
                    base_dn, bind_dn, bind_secret_ciphertext, user_filter, login_attribute,
                    subject_attribute, email_attribute, display_name_attribute, group_attribute,
                    jit_enabled, timeout_seconds, last_test_success
                ) VALUES (
                    :id, :tenant, 'ldap', 'active', 'ldaps://simulated.invalid', false,
                    'dc=cyrvanta,dc=demo', 'cn=simulated', :secret, '(uid={username})', 'uid',
                    'subject', 'mail', 'displayName', 'memberOf', true, 5, true
                )
                ON CONFLICT (tenant_id) DO UPDATE SET
                    status='active', server_uri='ldaps://simulated.invalid',
                    bind_secret_ciphertext=EXCLUDED.bind_secret_ciphertext, jit_enabled=true,
                    last_test_success=true
            """),
            {
                "id": uuid4(), "tenant": tenant_id,
                "secret": cipher.encrypt("simulated-no-network-secret"),
            },
        )
        await session.execute(
            text("""
                INSERT INTO directory_group_mappings (id, tenant_id, external_group, role_id)
                SELECT :id, :tenant, 'cyrvanta-demo-analysts', id FROM roles
                WHERE tenant_id=:tenant AND code='viewer'
                ON CONFLICT DO NOTHING
            """),
            {"id": uuid4(), "tenant": tenant_id},
        )
    print("Simulated directory configured")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-slug", required=True)
    args = parser.parse_args()
    asyncio.run(bootstrap(args.tenant_slug))


if __name__ == "__main__":
    main()
