"""Release the non-legacy simulated user-block workflow."""
# ruff: noqa: E501

import os

from alembic import op

revision = "0017_finalize_simulation"
down_revision = "0016_playbook_execution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    app_role = os.environ.get("POSTGRES_APP_ROLE", "cyrvanta_app")
    op.execute(
        """
        UPDATE automation_engine_bindings b
        SET active = false
        FROM playbook_versions v, playbook_definitions d
        WHERE b.playbook_version_id = v.id
          AND v.definition_id = d.id
          AND b.tenant_id = v.tenant_id
          AND v.tenant_id = d.tenant_id
          AND d.code = 'simulate-user-block'
          AND v.version = 'provisional-demo-1'
        """
    )
    op.execute(
        """
        INSERT INTO playbook_versions (
          tenant_id, definition_id, version, impact, classification, status,
          workflow_code, artifact_sha256, input_schema, result_schema,
          timeout_seconds, approved_at
        )
        SELECT d.tenant_id, d.id, '1.0.0', 'MODERATE', 'SYNTHETIC', 'APPROVED',
               'simulate-user-block', '97c0e94310daf21c92f3b45e89919935622d9db2354a5f53ac2b6600d121cfed',
               jsonb_build_object(
                 'type', 'object',
                 'additionalProperties', false,
                 'required', jsonb_build_array(
                   'targets', 'parameters', 'evidence_refs'
                 )
               ),
               jsonb_build_object(
                 'type', 'object',
                 'additionalProperties', false,
                 'required', jsonb_build_array(
                   'execution_mode', 'action', 'result'
                 ),
                 'properties', jsonb_build_object(
                   'execution_mode', jsonb_build_object('const', 'demo'),
                   'action', jsonb_build_object('const', 'block_user'),
                   'result', jsonb_build_object('const', 'simulated_success')
                 )
               ),
               120, now()
        FROM playbook_definitions d
        WHERE d.code = 'simulate-user-block'
        ON CONFLICT (tenant_id, definition_id, version) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO automation_engine_bindings (
          tenant_id, playbook_version_id, engine_type, instance_code,
          adapter_workflow_id, webhook_path, key_id, desired_digest,
          observed_digest, sync_status, active, last_verified_at
        )
        SELECT v.tenant_id, v.id, 'N8N', 'local-demo',
               'cyrvanta-simulate-user-block', 'simulate-user-block',
               'local-demo-v1', '97c0e94310daf21c92f3b45e89919935622d9db2354a5f53ac2b6600d121cfed', '97c0e94310daf21c92f3b45e89919935622d9db2354a5f53ac2b6600d121cfed',
               'SYNCHRONIZED', true, now()
        FROM playbook_versions v
        JOIN playbook_definitions d
          ON d.id = v.definition_id AND d.tenant_id = v.tenant_id
        WHERE d.code = 'simulate-user-block'
          AND v.version = '1.0.0'
        ON CONFLICT (tenant_id, playbook_version_id, instance_code) DO NOTHING
        """
    )
    op.execute("GRANT SELECT ON playbook_versions, automation_engine_bindings TO " + app_role)


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM playbook_executions e
            JOIN playbook_versions v
              ON v.id = e.playbook_version_id AND v.tenant_id = e.tenant_id
            JOIN playbook_definitions d
              ON d.id = v.definition_id AND d.tenant_id = v.tenant_id
            WHERE d.code = 'simulate-user-block' AND v.version = '1.0.0'
          )
          THEN
            RAISE EXCEPTION
              'released simulated user-block executions exist; export them before downgrade';
          END IF;
        END
        $$
        """
    )
    op.execute(
        """
        DELETE FROM automation_engine_bindings b
        USING playbook_versions v, playbook_definitions d
        WHERE b.playbook_version_id = v.id
          AND b.tenant_id = v.tenant_id
          AND v.definition_id = d.id
          AND v.tenant_id = d.tenant_id
          AND d.code = 'simulate-user-block'
          AND v.version = '1.0.0'
        """
    )
    op.execute(
        """
        DELETE FROM playbook_versions v
        USING playbook_definitions d
        WHERE v.definition_id = d.id
          AND v.tenant_id = d.tenant_id
          AND d.code = 'simulate-user-block'
          AND v.version = '1.0.0'
        """
    )
