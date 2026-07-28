"""Add versioned canonical finding provenance."""

import os
import re

from alembic import op

revision = "0009_finding_provenance"
down_revision = "0008_event_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    app_role = os.environ.get("POSTGRES_APP_USER", "cyrvanta_app")
    if re.fullmatch(r"[a-z_][a-z0-9_]*", app_role) is None:
        raise ValueError("POSTGRES_APP_USER is not a safe PostgreSQL identifier")

    ddl = """
        ALTER TABLE alert_references
          ADD COLUMN integration_id uuid,
          ADD COLUMN current_revision_id uuid,
          ADD COLUMN current_revision_number integer,
          ADD CONSTRAINT ck_alert_current_revision_number
            CHECK (
              current_revision_number IS NULL OR current_revision_number > 0
            ),
          ADD CONSTRAINT uq_alert_references_id_tenant UNIQUE (id, tenant_id);

        ALTER TABLE alert_references
          DROP CONSTRAINT alert_references_tenant_id_source_external_id_key;

        CREATE UNIQUE INDEX uq_alert_reference_canonical_identity
          ON alert_references (
            tenant_id, integration_id, source, external_id
          )
          WHERE integration_id IS NOT NULL;

        CREATE UNIQUE INDEX uq_alert_reference_legacy_identity
          ON alert_references (tenant_id, source, external_id)
          WHERE integration_id IS NULL;

        CREATE TABLE finding_revisions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          alert_reference_id uuid NOT NULL,
          revision_number integer NOT NULL CHECK (revision_number > 0),
          integration_id uuid NOT NULL,
          source_system varchar(80) NOT NULL,
          source_instance_id uuid NOT NULL,
          source_object_type varchar(80) NOT NULL,
          source_object_id varchar(512) NOT NULL,
          source_occurred_at timestamptz,
          observed_at timestamptz NOT NULL,
          effective_at timestamptz NOT NULL,
          effective_time_basis varchar(16) NOT NULL CHECK (
            effective_time_basis IN ('SOURCE', 'DERIVED', 'INGESTED')
          ),
          title varchar(500) NOT NULL,
          description text CHECK (
            description IS NULL OR length(description) <= 4000
          ),
          severity_score smallint NOT NULL CHECK (
            severity_score BETWEEN 0 AND 100
          ),
          confidence numeric(5,4) CHECK (
            confidence IS NULL OR confidence BETWEEN 0 AND 1
          ),
          category varchar(120),
          external_status varchar(80) NOT NULL,
          rule_reference varchar(200),
          entity_references jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (
            jsonb_typeof(entity_references) = 'array'
            AND jsonb_array_length(entity_references) <= 32
          ),
          evidence_locator varchar(2048) NOT NULL,
          payload_sha256 varchar(64) NOT NULL CHECK (
            payload_sha256 ~ '^[0-9a-f]{64}$'
          ),
          fingerprint_mode varchar(32) NOT NULL CHECK (
            fingerprint_mode IN ('RAW_DOCUMENT', 'ADAPTER_MATERIAL')
          ),
          fingerprint_version varchar(20) NOT NULL,
          adapter_name varchar(80) NOT NULL,
          adapter_version varchar(40) NOT NULL,
          normalizer_version varchar(40) NOT NULL,
          canonical_schema_version integer NOT NULL CHECK (
            canonical_schema_version > 0
          ),
          normalization_status varchar(16) NOT NULL CHECK (
            normalization_status IN ('VALID', 'PARTIAL')
          ),
          completeness_score smallint NOT NULL CHECK (
            completeness_score BETWEEN 0 AND 100
          ),
          issue_codes varchar(80)[] NOT NULL DEFAULT '{}',
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_finding_revision_alert_tenant
            FOREIGN KEY (alert_reference_id, tenant_id)
            REFERENCES alert_references(id, tenant_id),
          CONSTRAINT uq_finding_revision_id_tenant UNIQUE (id, tenant_id),
          CONSTRAINT uq_finding_revision_number
            UNIQUE (tenant_id, alert_reference_id, revision_number),
          CONSTRAINT uq_finding_revision_payload
            UNIQUE (
              tenant_id, integration_id, source_object_type,
              source_object_id, payload_sha256
            )
        );

        ALTER TABLE alert_references
          ADD CONSTRAINT fk_alert_current_revision_tenant
          FOREIGN KEY (current_revision_id, tenant_id)
          REFERENCES finding_revisions(id, tenant_id);

        CREATE INDEX ix_finding_revisions_tenant_effective
          ON finding_revisions(tenant_id, effective_at DESC);
        CREATE INDEX ix_finding_revisions_tenant_source
          ON finding_revisions(
            tenant_id, integration_id, source_object_type, source_object_id
          );

        ALTER TABLE finding_revisions ENABLE ROW LEVEL SECURITY;
        ALTER TABLE finding_revisions FORCE ROW LEVEL SECURITY;
        CREATE POLICY finding_revisions_tenant_isolation ON finding_revisions
          USING (
            tenant_id =
            nullif(current_setting('app.current_tenant_id', true), '')::uuid
          )
          WITH CHECK (
            tenant_id =
            nullif(current_setting('app.current_tenant_id', true), '')::uuid
          );
        """
    for statement in ddl.split(";"):
        if statement.strip():
            op.execute(statement)
    op.execute(f"GRANT SELECT, INSERT ON finding_revisions TO {app_role}")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM finding_revisions)
             OR EXISTS (
               SELECT 1 FROM alert_references
               WHERE integration_id IS NOT NULL
             )
          THEN
            RAISE EXCEPTION
              'canonical finding data exists; back up and remove it before downgrade';
          END IF;
        END
        $$;
        """
    )
    op.execute(
        "ALTER TABLE alert_references DROP CONSTRAINT fk_alert_current_revision_tenant"
    )
    op.execute("DROP TABLE finding_revisions")
    op.execute("DROP INDEX uq_alert_reference_legacy_identity")
    op.execute("DROP INDEX uq_alert_reference_canonical_identity")
    op.execute(
        """
        ALTER TABLE alert_references
          DROP CONSTRAINT uq_alert_references_id_tenant,
          DROP CONSTRAINT ck_alert_current_revision_number,
          DROP COLUMN current_revision_number,
          DROP COLUMN current_revision_id,
          DROP COLUMN integration_id
        """
    )
    op.execute(
        """
        ALTER TABLE alert_references
          ADD CONSTRAINT alert_references_tenant_id_source_external_id_key
          UNIQUE (tenant_id, source, external_id)
        """
    )
