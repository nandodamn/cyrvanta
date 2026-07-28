"""Add versioned ATT&CK, deterministic risk, and explanations."""

import os
import re

from alembic import op

revision = "0014_attack_risk"
down_revision = "0013_correlation_tenant_fks"
branch_labels = None
depends_on = None


def _statements(ddl: str) -> None:
    for statement in ddl.split(";"):
        if statement.strip():
            op.execute(statement)


def upgrade() -> None:
    app_role = os.environ.get("POSTGRES_APP_USER", "cyrvanta_app")
    if re.fullmatch(r"[a-z_][a-z0-9_]*", app_role) is None:
        raise ValueError("POSTGRES_APP_USER is not a safe PostgreSQL identifier")
    _statements(
        """
        ALTER TABLE incident_timeline_entries
          ADD CONSTRAINT uq_incident_timeline_id_tenant UNIQUE (id, tenant_id);

        CREATE TABLE attack_releases (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          domain varchar(40) NOT NULL CHECK (domain = 'enterprise-attack'),
          version varchar(40) NOT NULL,
          stix_version varchar(16) NOT NULL CHECK (stix_version = '2.1'),
          source_url varchar(2048) NOT NULL,
          bundle_sha256 varchar(64) NOT NULL CHECK (bundle_sha256 ~ '^[0-9a-f]{64}$'),
          status varchar(16) NOT NULL CHECK (status IN ('IMPORTED','ACTIVE','RETIRED')),
          imported_at timestamptz NOT NULL DEFAULT now(),
          activated_at timestamptz,
          CONSTRAINT uq_attack_release_version UNIQUE (domain, version)
        );
        CREATE UNIQUE INDEX uq_attack_release_active
          ON attack_releases(domain) WHERE status = 'ACTIVE';

        CREATE TABLE attack_objects (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          release_id uuid NOT NULL REFERENCES attack_releases(id),
          stix_id varchar(160) NOT NULL,
          object_type varchar(40) NOT NULL CHECK (
            object_type IN ('x-mitre-tactic','attack-pattern','course-of-action',
                            'marking-definition')
          ),
          external_id varchar(40),
          name_en varchar(500),
          description_en text,
          is_subtechnique boolean NOT NULL,
          revoked boolean NOT NULL,
          deprecated boolean NOT NULL,
          tactic_codes varchar(80)[] NOT NULL DEFAULT '{}',
          modified timestamptz,
          CONSTRAINT uq_attack_object_stix UNIQUE (release_id, stix_id)
        );
        CREATE INDEX ix_attack_object_external
          ON attack_objects(release_id, external_id);

        CREATE TABLE attack_relationships (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          release_id uuid NOT NULL REFERENCES attack_releases(id),
          stix_id varchar(160) NOT NULL,
          relationship_type varchar(80) NOT NULL,
          source_stix_id varchar(160) NOT NULL,
          target_stix_id varchar(160) NOT NULL,
          revoked boolean NOT NULL,
          CONSTRAINT uq_attack_relationship_stix UNIQUE (release_id, stix_id)
        );
        CREATE INDEX ix_attack_relationship_source
          ON attack_relationships(release_id, source_stix_id);

        CREATE TABLE threat_mapping_rule_versions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          rule_code varchar(120) NOT NULL,
          version varchar(40) NOT NULL,
          status varchar(16) NOT NULL CHECK (status IN ('DRAFT','ACTIVE','RETIRED')),
          definition jsonb NOT NULL CHECK (jsonb_typeof(definition) = 'object'),
          definition_sha256 varchar(64) NOT NULL CHECK (
            definition_sha256 ~ '^[0-9a-f]{64}$'
          ),
          activated_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_threat_mapping_rule_version UNIQUE (rule_code, version)
        );
        CREATE UNIQUE INDEX uq_threat_mapping_rule_active
          ON threat_mapping_rule_versions(rule_code) WHERE status = 'ACTIVE';

        CREATE TABLE risk_definition_versions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          code varchar(120) NOT NULL,
          version varchar(40) NOT NULL,
          status varchar(16) NOT NULL CHECK (status IN ('DRAFT','ACTIVE','RETIRED')),
          definition jsonb NOT NULL CHECK (jsonb_typeof(definition) = 'object'),
          definition_sha256 varchar(64) NOT NULL CHECK (
            definition_sha256 ~ '^[0-9a-f]{64}$'
          ),
          activated_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_risk_definition_version UNIQUE (code, version)
        );
        CREATE UNIQUE INDEX uq_risk_definition_active
          ON risk_definition_versions(code) WHERE status = 'ACTIVE';

        CREATE TABLE incident_attack_mappings (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          incident_id uuid NOT NULL,
          attack_object_id uuid NOT NULL REFERENCES attack_objects(id),
          mapping_rule_id uuid NOT NULL REFERENCES threat_mapping_rule_versions(id),
          correlation_run_id uuid NOT NULL,
          status varchar(16) NOT NULL CHECK (
            status IN ('PROPOSED','SUPPORTED','VALIDATED','REJECTED','SUPERSEDED')
          ),
          selector_codes varchar(120)[] NOT NULL CHECK (
            cardinality(selector_codes) BETWEEN 1 AND 32
          ),
          fingerprint varchar(64) NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
          supersedes_id uuid,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_incident_attack_mapping_id_tenant UNIQUE (id, tenant_id),
          CONSTRAINT uq_incident_attack_mapping_fingerprint UNIQUE (tenant_id, fingerprint),
          CONSTRAINT fk_attack_mapping_incident_tenant FOREIGN KEY (incident_id, tenant_id)
            REFERENCES incidents(id, tenant_id),
          CONSTRAINT fk_attack_mapping_correlation_tenant
            FOREIGN KEY (correlation_run_id, tenant_id)
            REFERENCES correlation_runs(id, tenant_id),
          CONSTRAINT fk_attack_mapping_supersedes_tenant
            FOREIGN KEY (supersedes_id, tenant_id)
            REFERENCES incident_attack_mappings(id, tenant_id)
        );

        CREATE TABLE attack_mapping_evidence (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          mapping_id uuid NOT NULL,
          evidence_type varchar(40) NOT NULL CHECK (
            evidence_type IN ('FINDING_REVISION','CORRELATION_MATCH','CLAIM',
                              'INCIDENT_TIMELINE_ENTRY')
          ),
          finding_revision_id uuid,
          correlation_run_id uuid,
          claim_id uuid,
          timeline_entry_id uuid,
          sort_order integer NOT NULL CHECK (sort_order BETWEEN 0 AND 31),
          CONSTRAINT fk_mapping_evidence_mapping_tenant FOREIGN KEY (mapping_id, tenant_id)
            REFERENCES incident_attack_mappings(id, tenant_id),
          CONSTRAINT fk_mapping_evidence_finding_tenant
            FOREIGN KEY (finding_revision_id, tenant_id)
            REFERENCES finding_revisions(id, tenant_id),
          CONSTRAINT fk_mapping_evidence_correlation_tenant
            FOREIGN KEY (correlation_run_id, tenant_id)
            REFERENCES correlation_runs(id, tenant_id),
          CONSTRAINT fk_mapping_evidence_claim_tenant FOREIGN KEY (claim_id, tenant_id)
            REFERENCES claims(id, tenant_id),
          CONSTRAINT fk_mapping_evidence_timeline_tenant
            FOREIGN KEY (timeline_entry_id, tenant_id)
            REFERENCES incident_timeline_entries(id, tenant_id),
          CONSTRAINT ck_mapping_evidence_one_reference CHECK (
            num_nonnulls(finding_revision_id, correlation_run_id, claim_id,
                         timeline_entry_id) = 1
          ),
          CONSTRAINT uq_mapping_evidence_order UNIQUE (tenant_id, mapping_id, sort_order)
        );

        CREATE TABLE risk_assessments (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          incident_id uuid NOT NULL,
          definition_id uuid NOT NULL REFERENCES risk_definition_versions(id),
          correlation_run_id uuid NOT NULL,
          score smallint NOT NULL CHECK (score BETWEEN 0 AND 100),
          band varchar(16) NOT NULL CHECK (
            band IN ('minimal','low','medium','high','critical')
          ),
          input_snapshot jsonb NOT NULL CHECK (jsonb_typeof(input_snapshot) = 'object'),
          fingerprint varchar(64) NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
          supersedes_id uuid,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_risk_assessment_id_tenant UNIQUE (id, tenant_id),
          CONSTRAINT uq_risk_assessment_fingerprint
            UNIQUE (tenant_id, incident_id, fingerprint),
          CONSTRAINT fk_risk_incident_tenant FOREIGN KEY (incident_id, tenant_id)
            REFERENCES incidents(id, tenant_id),
          CONSTRAINT fk_risk_correlation_tenant FOREIGN KEY (correlation_run_id, tenant_id)
            REFERENCES correlation_runs(id, tenant_id),
          CONSTRAINT fk_risk_supersedes_tenant FOREIGN KEY (supersedes_id, tenant_id)
            REFERENCES risk_assessments(id, tenant_id)
        );

        CREATE TABLE risk_assessment_factors (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          assessment_id uuid NOT NULL,
          factor_code varchar(120) NOT NULL,
          weight smallint NOT NULL CHECK (weight BETWEEN 0 AND 100),
          contribution smallint NOT NULL CHECK (contribution BETWEEN 0 AND weight),
          evidence_snapshot jsonb NOT NULL CHECK (jsonb_typeof(evidence_snapshot) = 'object'),
          CONSTRAINT fk_risk_factor_assessment_tenant
            FOREIGN KEY (assessment_id, tenant_id)
            REFERENCES risk_assessments(id, tenant_id),
          CONSTRAINT uq_risk_factor_code UNIQUE (tenant_id, assessment_id, factor_code)
        );

        CREATE TABLE incident_explanations (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          incident_id uuid NOT NULL,
          risk_assessment_id uuid NOT NULL,
          locale varchar(5) NOT NULL CHECK (locale IN ('es','en')),
          mode varchar(24) NOT NULL CHECK (mode IN ('DETERMINISTIC','AI_REDACTION')),
          provider varchar(80) NOT NULL,
          model varchar(120),
          text text NOT NULL CHECK (length(text) BETWEEN 1 AND 4000),
          grounded boolean NOT NULL,
          input_fingerprint varchar(64) NOT NULL CHECK (
            input_fingerprint ~ '^[0-9a-f]{64}$'
          ),
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_explanation_incident_tenant FOREIGN KEY (incident_id, tenant_id)
            REFERENCES incidents(id, tenant_id),
          CONSTRAINT fk_explanation_risk_tenant FOREIGN KEY (risk_assessment_id, tenant_id)
            REFERENCES risk_assessments(id, tenant_id),
          CONSTRAINT uq_incident_explanation
            UNIQUE (tenant_id, risk_assessment_id, locale, mode)
        );

        CREATE INDEX ix_attack_mapping_incident
          ON incident_attack_mappings(tenant_id, incident_id, created_at DESC);
        CREATE INDEX ix_attack_mapping_evidence
          ON attack_mapping_evidence(tenant_id, mapping_id, sort_order);
        CREATE INDEX ix_risk_assessment_incident
          ON risk_assessments(tenant_id, incident_id, created_at DESC);
        CREATE INDEX ix_explanation_incident
          ON incident_explanations(tenant_id, incident_id, created_at DESC);
        """
    )
    tenant_tables = (
        "incident_attack_mappings",
        "attack_mapping_evidence",
        "risk_assessments",
        "risk_assessment_factors",
        "incident_explanations",
    )
    for table in tenant_tables:
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
        WITH mapping_material AS (
          SELECT '{
            "rule_code":"credential-attack",
            "rule_version":"2",
            "mappings":{
              "auth_failure":"T1110",
              "auth_success":"T1078",
              "privilege_change":"T1098"
            }
          }'::jsonb definition
        )
        INSERT INTO threat_mapping_rule_versions (
          rule_code, version, status, definition, definition_sha256, activated_at
        )
        SELECT 'credential-attack', '2', 'ACTIVE', definition,
               encode(digest(definition::text, 'sha256'), 'hex'), now()
        FROM mapping_material
        """
    )
    op.execute(
        """
        WITH risk_material AS (
          SELECT '{
            "code":"incident-risk",
            "version":"1",
            "factors":[
              {"code":"incident_severity","max": 60},
              {"code":"evidence_corroboration","max": 15},
              {"code":"source_diversity","max": 10},
              {"code":"supported_attack_mappings","max": 10},
              {"code":"normalization_quality","max": 5}
            ],
            "bands":{"minimal":[0,19],"low":[20,39],"medium":[40,59],
                     "high":[60,79],"critical":[80,100]}
          }'::jsonb definition
        )
        INSERT INTO risk_definition_versions (
          code, version, status, definition, definition_sha256, activated_at
        )
        SELECT 'incident-risk', '1', 'ACTIVE', definition,
               encode(digest(definition::text, 'sha256'), 'hex'), now()
        FROM risk_material
        """
    )
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
          ('mitre.catalog.read', 'Read the active versioned ATT&CK catalog'),
          ('mitre.mapping.read', 'Read tenant ATT&CK evidence mappings'),
          ('mitre.mapping.validate', 'Validate tenant ATT&CK evidence mappings'),
          ('risk.read', 'Read deterministic tenant risk assessments'),
          ('risk.recalculate', 'Create deterministic tenant risk assessments'),
          ('explanation.read', 'Read grounded tenant explanations'),
          ('explanation.generate', 'Generate grounded tenant explanations'),
          ('threat-knowledge.manage', 'Manage global threat knowledge releases')
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
            'mitre.catalog.read','mitre.mapping.read','mitre.mapping.validate',
            'risk.read','risk.recalculate','explanation.read',
            'explanation.generate'
          )
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        "GRANT SELECT, INSERT ON attack_releases, attack_objects, "
        f"attack_relationships TO {app_role}"
    )
    op.execute(f"GRANT UPDATE (status, activated_at) ON attack_releases TO {app_role}")
    op.execute(
        "GRANT SELECT ON threat_mapping_rule_versions, risk_definition_versions "
        f"TO {app_role}"
    )
    op.execute(
        "GRANT SELECT, INSERT ON incident_attack_mappings, attack_mapping_evidence, "
        "risk_assessments, risk_assessment_factors, incident_explanations "
        f"TO {app_role}"
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM incident_attack_mappings)
             OR EXISTS (SELECT 1 FROM risk_assessments)
             OR EXISTS (SELECT 1 FROM attack_releases)
          THEN
            RAISE EXCEPTION
              'ATT&CK or risk data exists; back up and remove it before downgrade';
          END IF;
        END
        $$;
        """
    )
    _statements(
        """
        DROP TABLE incident_explanations;
        DROP TABLE risk_assessment_factors;
        DROP TABLE risk_assessments;
        DROP TABLE attack_mapping_evidence;
        DROP TABLE incident_attack_mappings;
        DROP TABLE risk_definition_versions;
        DROP TABLE threat_mapping_rule_versions;
        DROP TABLE attack_relationships;
        DROP TABLE attack_objects;
        DROP TABLE attack_releases;
        ALTER TABLE incident_timeline_entries
          DROP CONSTRAINT uq_incident_timeline_id_tenant;
        """
    )
