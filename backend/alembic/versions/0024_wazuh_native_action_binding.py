# ruff: noqa: E501
"""Allow native action bindings to target the tenant's Wazuh manager.

host.isolate / host.restore reach Wazuh Active Response over the manager's
authenticated HTTPS API, so their binding needs to carry a credential just like
the SMTP and HTTP allowlisted connectors do. The original constraint predates
those actions and only knew about SIMULATED/INTERNAL (credential-less) and
HTTP_ALLOWLISTED/SMTP (credential-bearing), which made a Wazuh binding
impossible to persist at all.
"""

from alembic import op

revision = "0024_wazuh_action_binding"
down_revision = "0023_default_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE native_action_bindings
            DROP CONSTRAINT IF EXISTS native_action_bindings_connector_type_check
        """
    )
    op.execute(
        """
        ALTER TABLE native_action_bindings
            ADD CONSTRAINT native_action_bindings_connector_type_check
            CHECK (connector_type IN ('SIMULATED', 'HTTP_ALLOWLISTED', 'INTERNAL', 'SMTP', 'WAZUH'))
        """
    )
    op.execute(
        """
        ALTER TABLE native_action_bindings
            DROP CONSTRAINT IF EXISTS ck_native_action_binding_credential
        """
    )
    op.execute(
        """
        ALTER TABLE native_action_bindings
            ADD CONSTRAINT ck_native_action_binding_credential
            CHECK (
                (connector_type IN ('SIMULATED', 'INTERNAL') AND credential_key_id IS NULL)
                OR (connector_type IN ('HTTP_ALLOWLISTED', 'SMTP', 'WAZUH'))
            )
        """
    )


def downgrade() -> None:
    # Any Wazuh binding must go before the narrower constraints can be restored.
    op.execute("DELETE FROM native_action_bindings WHERE connector_type = 'WAZUH'")
    op.execute(
        """
        ALTER TABLE native_action_bindings
            DROP CONSTRAINT IF EXISTS ck_native_action_binding_credential
        """
    )
    op.execute(
        """
        ALTER TABLE native_action_bindings
            ADD CONSTRAINT ck_native_action_binding_credential
            CHECK (
                (connector_type IN ('SIMULATED', 'INTERNAL') AND credential_key_id IS NULL)
                OR (connector_type IN ('HTTP_ALLOWLISTED', 'SMTP'))
            )
        """
    )
    op.execute(
        """
        ALTER TABLE native_action_bindings
            DROP CONSTRAINT IF EXISTS native_action_bindings_connector_type_check
        """
    )
    op.execute(
        """
        ALTER TABLE native_action_bindings
            ADD CONSTRAINT native_action_bindings_connector_type_check
            CHECK (connector_type IN ('SIMULATED', 'HTTP_ALLOWLISTED', 'INTERNAL', 'SMTP'))
        """
    )
