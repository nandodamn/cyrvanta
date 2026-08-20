"""Seed the SOC roles the segregation of duties depends on.

Every tenant had exactly two roles: `tenant-admin`, holding all 55 permissions,
and whatever the tenant had built for itself. In the demo tenant that second
role was `viewer` with **zero** permissions, which left a real user
(ldap-demo@) able to sign in and do nothing at all. Segregation of duties
cannot be described, let alone demonstrated, when the only working role is an
administrator who can do everything.

Three roles are seeded as immutable, for every tenant present and future:

  soc-analyst     conducts an incident technically. Investigates, records
                  claims, requests responses, executes what was authorised,
                  and declares an incident technically resolved.
  soc-supervisor  everything the analyst does, plus the decisions that must
                  belong to someone else: assigning, approving a response,
                  assessing another person's claim, and closing.
  auditor         reads everything and changes nothing.

They are `is_system = true`, which the administration service already refuses
to modify. Immutable rather than merely protected: a tenant that needs another
combination creates its own role, and the seeded one stays intact as the
reference an auditor can compare against.

`incident.resolve` is new, and splitting it out is the point. `incident.close`
was described as "Resolve, close, or reopen incidents" -- one permission for
all three -- so declaring an incident technically resolved required the same
authority as closing it, which is exactly the separation this is meant to
create. Resolving is now the analyst's; closing and reopening stay with the
supervisor.

The role a user holds decides what they may ever attempt. Whether they may do
it to a particular incident -- as its technical owner, at its current state --
is decided in code, not here, precisely because role membership is editable
and that invariant must not be.

Revision ID: 0027_soc_system_roles
Revises: 0026_tenant_scoped_rules
"""

from alembic import op

revision = "0027_soc_system_roles"
down_revision = "0026_tenant_scoped_rules"
branch_labels = None
depends_on = None

NEW_PERMISSIONS: dict[str, str] = {
    "incident.resolve": "Declare an incident technically resolved",
}

# Read-only across every module. An auditor must be able to reconstruct what
# happened without being able to alter any part of it.
AUDITOR: tuple[str, ...] = (
    "alert.read",
    "audit.read",
    "claim.read",
    "correlation.read",
    "directory.read",
    "explanation.read",
    "feedback.read",
    "incident.read",
    "integration.read",
    "memory.metrics.read",
    "memory.read",
    "mitre.catalog.read",
    "mitre.mapping.read",
    "playbook.execution.read",
    "playbook.read",
    "playbook.view",
    "response.read",
    "risk.read",
    "role.read",
    "tenant.read",
    "user.read",
)

# Conducts the incident. Notably absent: incident.close (closing is someone
# else's judgement), incident.assign (they do not choose their own workload),
# claim.assess (a claim is assessed "independently", which means by another
# person), and response.approve (proposing and approving must not be the same
# hand).
ANALYST: tuple[str, ...] = (
    "alert.read",
    "analysis.request",
    "audit.read",
    "claim.create",
    "claim.read",
    "claim.translate",
    "correlation.read",
    "explanation.generate",
    "explanation.read",
    "feedback.create",
    "feedback.read",
    "incident.create",
    "incident.read",
    "incident.resolve",
    "incident.update",
    "memory.propose",
    "memory.read",
    "mitre.catalog.read",
    "mitre.mapping.read",
    "playbook.execution.read",
    "playbook.read",
    "playbook.view",
    "response.execute",
    "response.read",
    "response.request",
    "risk.read",
)

# The analyst's set plus the decisions that exist to be taken by someone other
# than whoever did the work.
SUPERVISOR: tuple[str, ...] = (
    *ANALYST,
    "claim.assess",
    "claim.retract",
    "incident.assign",
    "incident.close",
    "memory.review",
    "playbook.review",
    "response.approve",
    "response.cancel",
    "response.revoke",
    "risk.recalculate",
)

ROLES: dict[str, tuple[str, tuple[str, ...]]] = {
    "soc-analyst": ("Analista SOC", ANALYST),
    "soc-supervisor": ("Supervisor SOC", SUPERVISOR),
    "auditor": ("Auditor", AUDITOR),
}


def _quoted(codes: tuple[str, ...]) -> str:
    return ", ".join(f"'{code}'" for code in sorted(set(codes)))


def upgrade() -> None:
    values = ", ".join(f"('{code}', '{text}')" for code, text in NEW_PERMISSIONS.items())
    op.execute(
        f"INSERT INTO permissions (code, description) VALUES {values} "
        "ON CONFLICT (code) DO NOTHING"
    )

    for code, (name, permissions) in ROLES.items():
        # Per-tenant context throughout: alembic connects as a role subject to
        # forced row-level security, so a plain INSERT ... SELECT over roles or
        # role_permissions reads and writes nothing, silently.
        op.execute(
            f"""
            DO $$
            DECLARE tenant RECORD;
            BEGIN
              FOR tenant IN SELECT id FROM tenants LOOP
                PERFORM set_config('app.current_tenant_id', tenant.id::text, true);

                INSERT INTO roles (tenant_id, code, name, is_system)
                VALUES (tenant.id, '{code}', '{name}', true)
                ON CONFLICT DO NOTHING;

                INSERT INTO role_permissions (tenant_id, role_id, permission_id)
                SELECT tenant.id, r.id, p.id
                FROM roles r CROSS JOIN permissions p
                WHERE r.tenant_id = tenant.id
                  AND r.code = '{code}'
                  AND p.code IN ({_quoted(permissions)})
                ON CONFLICT DO NOTHING;
              END LOOP;
              PERFORM set_config('app.current_tenant_id', '', true);
            END $$;
            """
        )

    # tenant-admin keeps everything, including the new permission, so an
    # existing administrator does not lose the ability to resolve an incident.
    op.execute(
        f"""
        DO $$
        DECLARE tenant RECORD;
        BEGIN
          FOR tenant IN SELECT id FROM tenants LOOP
            PERFORM set_config('app.current_tenant_id', tenant.id::text, true);
            INSERT INTO role_permissions (tenant_id, role_id, permission_id)
            SELECT tenant.id, r.id, p.id
            FROM roles r CROSS JOIN permissions p
            WHERE r.tenant_id = tenant.id
              AND r.code = 'tenant-admin'
              AND p.code IN ({_quoted(tuple(NEW_PERMISSIONS))})
            ON CONFLICT DO NOTHING;
          END LOOP;
          PERFORM set_config('app.current_tenant_id', '', true);
        END $$;
        """
    )


def downgrade() -> None:
    codes = ", ".join(f"'{code}'" for code in sorted(ROLES))
    op.execute(
        f"""
        DO $$
        DECLARE tenant RECORD;
        BEGIN
          FOR tenant IN SELECT id FROM tenants LOOP
            PERFORM set_config('app.current_tenant_id', tenant.id::text, true);
            DELETE FROM user_roles
             WHERE role_id IN (SELECT id FROM roles WHERE tenant_id = tenant.id
                                 AND code IN ({codes}));
            DELETE FROM role_permissions
             WHERE role_id IN (SELECT id FROM roles WHERE tenant_id = tenant.id
                                 AND code IN ({codes}));
            DELETE FROM roles WHERE tenant_id = tenant.id AND code IN ({codes});
          END LOOP;
          PERFORM set_config('app.current_tenant_id', '', true);
        END $$;
        """
    )
    op.execute(
        f"""
        DELETE FROM role_permissions
        WHERE permission_id IN (SELECT id FROM permissions
                                 WHERE code IN ({_quoted(tuple(NEW_PERMISSIONS))}))
        """
    )
    op.execute(f"DELETE FROM permissions WHERE code IN ({_quoted(tuple(NEW_PERMISSIONS))})")
