"""Add tenant-isolated append-only epistemological claim ledger."""

import os
import re

from alembic import op

revision = "0010_claim_ledger"
down_revision = "0009_finding_provenance"
branch_labels = None
depends_on = None


def _execute_statements(ddl: str) -> None:
    for statement in ddl.split(";"):
        if statement.strip():
            op.execute(statement)


def upgrade() -> None:
    app_role = os.environ.get("POSTGRES_APP_USER", "cyrvanta_app")
    if re.fullmatch(r"[a-z_][a-z0-9_]*", app_role) is None:
        raise ValueError("POSTGRES_APP_USER is not a safe PostgreSQL identifier")

    _execute_statements(
        """
        ALTER TABLE incidents
          ADD CONSTRAINT uq_incidents_id_tenant UNIQUE (id, tenant_id);

        CREATE TABLE claims (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          incident_id uuid NOT NULL,
          claim_type varchar(32) NOT NULL CHECK (
            claim_type IN (
              'FACT','DERIVED_FACT','INFERENCE','HYPOTHESIS','RECOMMENDATION',
              'DECISION','ACTION','RESULT'
            )
            AND claim_type NOT IN ('DECISION','ACTION','RESULT')
          ),
          statement varchar(2000) NOT NULL CHECK (length(trim(statement)) > 0),
          language_code varchar(3) NOT NULL CHECK (
            language_code IN ('es','en','und')
          ),
          confidence numeric(5,4) CHECK (
            confidence IS NULL OR confidence BETWEEN 0 AND 1
          ),
          origin_type varchar(16) NOT NULL CHECK (
            origin_type IN ('SOURCE','HUMAN','RULE','SYSTEM','AI')
          ),
          origin_actor_user_id uuid REFERENCES users(id),
          origin_code varchar(120),
          origin_version varchar(80),
          provider varchar(80),
          model varchar(160),
          prompt_template_version varchar(80),
          output_schema_version varchar(80),
          input_fingerprint varchar(64) CHECK (
            input_fingerprint IS NULL
            OR input_fingerprint ~ '^[0-9a-f]{64}$'
          ),
          explanation text CHECK (
            explanation IS NULL OR length(explanation) <= 4000
          ),
          validation_criteria text CHECK (
            validation_criteria IS NULL OR length(validation_criteria) <= 2000
          ),
          missing_evidence varchar(80)[] NOT NULL DEFAULT '{}' CHECK (
            cardinality(missing_evidence) <= 16
          ),
          is_simulated boolean NOT NULL DEFAULT false,
          correlation_id uuid NOT NULL,
          causation_id uuid,
          idempotency_key varchar(64) CHECK (
            idempotency_key IS NULL
            OR idempotency_key ~ '^[0-9a-f]{64}$'
          ),
          schema_version integer NOT NULL DEFAULT 1 CHECK (schema_version > 0),
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_claim_incident_tenant
            FOREIGN KEY (incident_id, tenant_id)
            REFERENCES incidents(id, tenant_id),
          CONSTRAINT uq_claims_id_tenant UNIQUE (id, tenant_id),
          CONSTRAINT uq_claims_idempotency
            UNIQUE (tenant_id, incident_id, idempotency_key),
          CONSTRAINT ck_claim_confidence_type CHECK (
            (
              claim_type IN ('INFERENCE','HYPOTHESIS','RECOMMENDATION')
              AND confidence IS NOT NULL
            )
            OR (
              claim_type IN ('FACT','DERIVED_FACT')
              AND confidence IS NULL
            )
          ),
          CONSTRAINT ck_claim_human_actor CHECK (
            origin_type <> 'HUMAN' OR origin_actor_user_id IS NOT NULL
          ),
          CONSTRAINT ck_claim_ai_type CHECK (
            origin_type <> 'AI' OR claim_type <> 'FACT'
          ),
          CONSTRAINT ck_claim_hypothesis_criteria CHECK (
            claim_type <> 'HYPOTHESIS'
            OR length(trim(validation_criteria)) > 0
          )
        );

        CREATE TABLE claim_evidence_links (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          claim_id uuid NOT NULL,
          evidence_type varchar(40) NOT NULL CHECK (
            evidence_type IN (
              'FINDING_REVISION','ALERT_REFERENCE','INCIDENT',
              'INCIDENT_TIMELINE_ENTRY','AUDIT_EVENT','CLAIM'
            )
          ),
          evidence_id uuid NOT NULL,
          relationship varchar(16) NOT NULL CHECK (
            relationship IN ('SUPPORTS','REFUTES','CONTEXT')
          ),
          evidence_sha256 varchar(64) CHECK (
            evidence_sha256 IS NULL
            OR evidence_sha256 ~ '^[0-9a-f]{64}$'
          ),
          created_by_user_id uuid REFERENCES users(id),
          correlation_id uuid NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_claim_evidence_claim_tenant
            FOREIGN KEY (claim_id, tenant_id)
            REFERENCES claims(id, tenant_id),
          CONSTRAINT uq_claim_evidence_link UNIQUE (
            tenant_id, claim_id, evidence_type, evidence_id, relationship
          )
        );

        CREATE TABLE claim_relationships (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          source_claim_id uuid NOT NULL,
          target_claim_id uuid NOT NULL,
          relationship_type varchar(24) NOT NULL CHECK (
            relationship_type IN (
              'SUPPORTS','CONTRADICTS','DERIVED_FROM','SUPERSEDES','RESPONDS_TO'
            )
          ),
          created_by_user_id uuid REFERENCES users(id),
          producer varchar(120) NOT NULL,
          correlation_id uuid NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_claim_relationship_not_self CHECK (
            source_claim_id <> target_claim_id
          ),
          CONSTRAINT fk_claim_relationship_source_tenant
            FOREIGN KEY (source_claim_id, tenant_id)
            REFERENCES claims(id, tenant_id),
          CONSTRAINT fk_claim_relationship_target_tenant
            FOREIGN KEY (target_claim_id, tenant_id)
            REFERENCES claims(id, tenant_id),
          CONSTRAINT uq_claim_relationship UNIQUE (
            tenant_id, source_claim_id, target_claim_id, relationship_type
          )
        );

        CREATE TABLE claim_assessments (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          claim_id uuid NOT NULL,
          outcome varchar(32) NOT NULL CHECK (
            outcome IN (
              'VALIDATED','REJECTED','INSUFFICIENT_EVIDENCE','RETRACTED'
            )
          ),
          evaluator_user_id uuid REFERENCES users(id),
          evaluator_rule_code varchar(120),
          evaluator_rule_version varchar(80),
          explanation text NOT NULL CHECK (
            length(trim(explanation)) > 0 AND length(explanation) <= 4000
          ),
          correlation_id uuid NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_claim_assessment_claim_tenant
            FOREIGN KEY (claim_id, tenant_id)
            REFERENCES claims(id, tenant_id),
          CONSTRAINT ck_claim_assessment_evaluator CHECK (
            (evaluator_user_id IS NOT NULL
              AND evaluator_rule_code IS NULL
              AND evaluator_rule_version IS NULL)
            OR
            (evaluator_user_id IS NULL
              AND evaluator_rule_code IS NOT NULL
              AND evaluator_rule_version IS NOT NULL)
          )
        );

        CREATE TABLE claim_presentations (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          claim_id uuid NOT NULL,
          locale varchar(2) NOT NULL CHECK (locale IN ('es','en')),
          text varchar(2000) NOT NULL CHECK (length(trim(text)) > 0),
          version integer NOT NULL CHECK (version > 0),
          origin_type varchar(16) NOT NULL CHECK (
            origin_type IN ('HUMAN','RULE','AI')
          ),
          origin_actor_user_id uuid REFERENCES users(id),
          provider varchar(80),
          model varchar(160),
          correlation_id uuid NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_claim_presentation_claim_tenant
            FOREIGN KEY (claim_id, tenant_id)
            REFERENCES claims(id, tenant_id),
          CONSTRAINT uq_claim_presentation_version UNIQUE (
            tenant_id, claim_id, locale, version
          )
        );

        CREATE INDEX ix_claims_tenant_incident_time
          ON claims(tenant_id, incident_id, created_at DESC, id);
        CREATE INDEX ix_claims_tenant_type_time
          ON claims(tenant_id, claim_type, created_at DESC);
        CREATE INDEX ix_claim_evidence_tenant_claim
          ON claim_evidence_links(tenant_id, claim_id, created_at);
        CREATE INDEX ix_claim_relationship_target
          ON claim_relationships(tenant_id, target_claim_id, relationship_type);
        CREATE INDEX ix_claim_assessment_tenant_claim
          ON claim_assessments(tenant_id, claim_id, created_at DESC, id);
        CREATE INDEX ix_claim_presentation_tenant_claim_locale
          ON claim_presentations(tenant_id, claim_id, locale, version DESC);
        """
    )

    for table in (
        "claims",
        "claim_evidence_links",
        "claim_relationships",
        "claim_assessments",
        "claim_presentations",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY {table}_tenant_isolation ON {table}
            USING (
              tenant_id =
              nullif(current_setting('app.current_tenant_id', true), '')::uuid
            )
            WITH CHECK (
              tenant_id =
              nullif(current_setting('app.current_tenant_id', true), '')::uuid
            )"""
        )

    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
          ('analysis.read', 'Read persisted incident analysis'),
          ('claim.read', 'Read epistemological claims'),
          ('claim.create', 'Create human claims'),
          ('claim.assess', 'Assess claims independently'),
          ('claim.translate', 'Create claim presentations'),
          ('claim.retract', 'Retract eligible claims')
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (tenant_id, role_id, permission_id)
        SELECT r.tenant_id, r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE r.code = 'tenant-admin'
          AND p.code IN (
            'analysis.read','claim.read','claim.create','claim.assess',
            'claim.translate','claim.retract'
          )
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        "GRANT SELECT, INSERT ON "
        "claims, claim_evidence_links, claim_relationships, "
        f"claim_assessments, claim_presentations TO {app_role}"
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM claims)
             OR EXISTS (SELECT 1 FROM claim_evidence_links)
             OR EXISTS (SELECT 1 FROM claim_relationships)
             OR EXISTS (SELECT 1 FROM claim_assessments)
             OR EXISTS (SELECT 1 FROM claim_presentations)
          THEN
            RAISE EXCEPTION
              'claim ledger contains data; back up and remove it before downgrade';
          END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
          SELECT id FROM permissions
          WHERE code IN (
            'analysis.read','claim.read','claim.create','claim.assess',
            'claim.translate','claim.retract'
          )
        )
        """
    )
    op.execute(
        """
        DELETE FROM permissions
        WHERE code IN (
          'analysis.read','claim.read','claim.create','claim.assess',
          'claim.translate','claim.retract'
        )
        """
    )
    for table in (
        "claim_presentations",
        "claim_assessments",
        "claim_relationships",
        "claim_evidence_links",
        "claims",
    ):
        op.execute(f"DROP TABLE {table}")
    op.execute("ALTER TABLE incidents DROP CONSTRAINT uq_incidents_id_tenant")
