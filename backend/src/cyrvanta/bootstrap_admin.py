import argparse
import asyncio
from uuid import uuid4

from pwdlib import PasswordHash
from sqlalchemy import text

from cyrvanta.shared.database import SessionFactory


async def bootstrap(
    tenant_name: str, tenant_slug: str, email: str, password: str, display_name: str
) -> None:
    normalized_email = email.lower()
    tenant_id = uuid4()
    user_id = uuid4()
    role_id = uuid4()
    password_hash = PasswordHash.recommended().hash(password)
    async with SessionFactory() as session, session.begin():
        await session.execute(text("SELECT set_config('app.auth_lookup', 'true', true)"))
        existing = await session.scalar(
            text("SELECT EXISTS (SELECT 1 FROM users WHERE email = :email)"),
            {"email": normalized_email},
        )
        if existing:
            print(f"Administrator already exists for {normalized_email}; no changes made")
            return
        await session.execute(
            text(
                "INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug) "
                "ON CONFLICT DO NOTHING"
            ),
            {"id": tenant_id, "name": tenant_name, "slug": tenant_slug},
        )
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
        await session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash, display_name)
                VALUES (:id, :tenant_id, :email, :password_hash, :display_name)
                ON CONFLICT (email) DO NOTHING
            """),
            {
                "id": user_id,
                "tenant_id": tenant_id,
                "email": normalized_email,
                "password_hash": password_hash,
                "display_name": display_name,
            },
        )
        await session.execute(
            text("""
                INSERT INTO roles (id, tenant_id, code, name)
                VALUES (:id, :tenant_id, 'tenant-admin', 'Tenant Administrator')
                ON CONFLICT (tenant_id, code) DO NOTHING
            """),
            {"id": role_id, "tenant_id": tenant_id},
        )
        await session.execute(
            text("""
                INSERT INTO user_roles (tenant_id, user_id, role_id)
                SELECT :tenant_id, u.id, r.id FROM users u, roles r
                WHERE u.email = :email AND r.tenant_id = :tenant_id AND r.code = 'tenant-admin'
                ON CONFLICT DO NOTHING
            """),
            {"tenant_id": tenant_id, "email": normalized_email},
        )
    print(f"Bootstrap completed for {normalized_email} (tenant {tenant_id})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the initial tenant administrator")
    parser.add_argument("--tenant-name", required=True)
    parser.add_argument("--tenant-slug", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--display-name", default="Cyrvanta Administrator")
    args = parser.parse_args()
    asyncio.run(
        bootstrap(
            args.tenant_name,
            args.tenant_slug,
            args.email,
            args.password,
            args.display_name,
        )
    )


if __name__ == "__main__":
    main()
