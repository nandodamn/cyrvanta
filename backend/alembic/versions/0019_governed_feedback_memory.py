# ruff: noqa: E501, S608
"""Add governed feedback and memory ledger."""

import os
import re

from alembic import op

revision = "0019_governed_memory"
down_revision = "0018_dispatch_outcomes"
branch_labels = None
depends_on = None

TABLES = (
    "feedback_entries",
    "memory_candidates",
    "memory_candidate_versions",
    "memory_reviews",
    "memory_state_events",
    "memory_influences",
    "memory_metric_definitions",
    "memory_metric_snapshots",
)
PERMISSIONS = (
    "feedback.read",
    "feedback.create",
    "memory.read",
    "memory.propose",
    "memory.review",
    "memory.activate",
    "memory.disable",
    "memory.metrics.read",
)


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
        CREATE TABLE feedback_entries (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id),
          resource_type varchar(32) NOT NULL CHECK (resource_type IN ('INCIDENT','FINDING','CLAIM','ACTION_PROPOSAL','PLAYBOOK_EXECUTION')),
          resource_id uuid NOT NULL, actor_user_id uuid NOT NULL, outcome varchar(32) NOT NULL CHECK (outcome IN ('TRUE_POSITIVE','FALSE_POSITIVE','BENIGN_TRUE_POSITIVE','INCONCLUSIVE','ACTION_EFFECTIVE','ACTION_INEFFECTIVE','ACTION_PARTIAL','NOT_ASSESSED')),
          reason text NOT NULL CHECK (length(reason) BETWEEN 1 AND 1000), is_synthetic boolean NOT NULL DEFAULT false,
          idempotency_key varchar(200) NOT NULL, correlation_id uuid NOT NULL, occurred_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE (tenant_id, id), UNIQUE (tenant_id, idempotency_key),
          FOREIGN KEY (actor_user_id, tenant_id) REFERENCES users(id, tenant_id)
        );
        CREATE TABLE memory_candidates (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id),
          kind varchar(24) NOT NULL CHECK (kind IN ('CASE_NOTE','TREND')), source_type varchar(24) NOT NULL CHECK (source_type IN ('HUMAN','AI_SUGGESTED')),
          created_by_user_id uuid NOT NULL, idempotency_key varchar(200) NOT NULL, correlation_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE (tenant_id, id), UNIQUE (tenant_id, idempotency_key),
          FOREIGN KEY (created_by_user_id, tenant_id) REFERENCES users(id, tenant_id)
        );
        CREATE TABLE memory_candidate_versions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id), candidate_id uuid NOT NULL, version integer NOT NULL CHECK (version > 0),
          title_es varchar(200) NOT NULL, title_en varchar(200) NOT NULL, statement_es text NOT NULL CHECK (length(statement_es) BETWEEN 1 AND 2000), statement_en text NOT NULL CHECK (length(statement_en) BETWEEN 1 AND 2000),
          conditions jsonb NOT NULL CHECK (jsonb_typeof(conditions) = 'object'), evidence_refs jsonb NOT NULL CHECK (jsonb_typeof(evidence_refs) = 'array' AND jsonb_array_length(evidence_refs) BETWEEN 1 AND 100),
          is_synthetic boolean NOT NULL, valid_from timestamptz NOT NULL, valid_until timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE (tenant_id, id), UNIQUE (tenant_id, candidate_id, version),
          CHECK (valid_until > valid_from AND valid_until <= valid_from + interval '90 days'),
          FOREIGN KEY (candidate_id, tenant_id) REFERENCES memory_candidates(id, tenant_id)
        );
        CREATE TABLE memory_reviews (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id), version_id uuid NOT NULL, reviewer_user_id uuid NOT NULL,
          decision varchar(24) NOT NULL CHECK (decision IN ('APPROVE','REJECT','REQUEST_CHANGES')), reason text NOT NULL CHECK (length(reason) BETWEEN 1 AND 1000), created_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE (tenant_id, id), UNIQUE (tenant_id, version_id, reviewer_user_id),
          FOREIGN KEY (version_id, tenant_id) REFERENCES memory_candidate_versions(id, tenant_id), FOREIGN KEY (reviewer_user_id, tenant_id) REFERENCES users(id, tenant_id)
        );
        CREATE TABLE memory_state_events (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id), version_id uuid NOT NULL, actor_user_id uuid,
          from_status varchar(24), to_status varchar(24) NOT NULL CHECK (to_status IN ('DRAFT','IN_REVIEW','APPROVED','ACTIVE','REJECTED','EXPIRED','DISABLED','SUPERSEDED')),
          reason text NOT NULL CHECK (length(reason) BETWEEN 1 AND 1000), occurred_at timestamptz NOT NULL, correlation_id uuid NOT NULL,
          UNIQUE (tenant_id, id), FOREIGN KEY (version_id, tenant_id) REFERENCES memory_candidate_versions(id, tenant_id), FOREIGN KEY (actor_user_id, tenant_id) REFERENCES users(id, tenant_id)
        );
        CREATE TABLE memory_influences (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id), version_id uuid NOT NULL,
          consumer_type varchar(80) NOT NULL, consumer_id uuid NOT NULL, matched boolean NOT NULL,
          base_fingerprint varchar(64) NOT NULL CHECK (base_fingerprint ~ '^[0-9a-f]{64}$'), presented_fingerprint varchar(64) NOT NULL CHECK (presented_fingerprint ~ '^[0-9a-f]{64}$'),
          explanation text NOT NULL CHECK (length(explanation) BETWEEN 1 AND 2000), idempotency_key varchar(200) NOT NULL, correlation_id uuid NOT NULL, occurred_at timestamptz NOT NULL,
          UNIQUE (tenant_id, id), UNIQUE (tenant_id, idempotency_key), FOREIGN KEY (version_id, tenant_id) REFERENCES memory_candidate_versions(id, tenant_id)
        );
        CREATE TABLE memory_metric_definitions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id), code varchar(120) NOT NULL, version integer NOT NULL CHECK (version > 0),
          definition_sha256 varchar(64) NOT NULL CHECK (definition_sha256 ~ '^[0-9a-f]{64}$'), window_days integer NOT NULL CHECK (window_days BETWEEN 1 AND 3650), minimum_sample_size integer NOT NULL CHECK (minimum_sample_size >= 20), active boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE (tenant_id, id), UNIQUE (tenant_id, code, version)
        );
        CREATE TABLE memory_metric_snapshots (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id), definition_id uuid NOT NULL,
          window_start timestamptz NOT NULL, window_end timestamptz NOT NULL, sample_size integer NOT NULL CHECK (sample_size >= 0), numerator integer NOT NULL CHECK (numerator >= 0), denominator integer NOT NULL CHECK (denominator > 0),
          value numeric(18,8) NOT NULL, sufficient_sample boolean NOT NULL, input_fingerprint varchar(64) NOT NULL CHECK (input_fingerprint ~ '^[0-9a-f]{64}$'), created_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE (tenant_id, id), CHECK (window_end > window_start AND numerator <= denominator), FOREIGN KEY (definition_id, tenant_id) REFERENCES memory_metric_definitions(id, tenant_id)
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION enforce_memory_review_separation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM memory_candidate_versions v JOIN memory_candidates c ON c.id=v.candidate_id AND c.tenant_id=v.tenant_id
            WHERE v.id=NEW.version_id AND v.tenant_id=NEW.tenant_id AND c.created_by_user_id=NEW.reviewer_user_id
          ) THEN RAISE EXCEPTION 'memory author cannot review own version'; END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION enforce_feedback_synthetic_provenance() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE source_is_synthetic boolean;
        BEGIN
          IF NEW.resource_type = 'INCIDENT' THEN
            SELECT is_simulated INTO source_is_synthetic FROM incidents WHERE id=NEW.resource_id AND tenant_id=NEW.tenant_id;
          ELSIF NEW.resource_type = 'FINDING' THEN
            SELECT a.is_simulated INTO source_is_synthetic FROM finding_revisions f JOIN alert_references a ON a.id=f.alert_reference_id AND a.tenant_id=f.tenant_id WHERE f.id=NEW.resource_id AND f.tenant_id=NEW.tenant_id;
          ELSIF NEW.resource_type = 'CLAIM' THEN
            SELECT is_simulated INTO source_is_synthetic FROM claims WHERE id=NEW.resource_id AND tenant_id=NEW.tenant_id;
          ELSIF NEW.resource_type = 'ACTION_PROPOSAL' THEN
            SELECT is_simulated INTO source_is_synthetic FROM action_proposals WHERE id=NEW.resource_id AND tenant_id=NEW.tenant_id;
          ELSIF NEW.resource_type = 'PLAYBOOK_EXECUTION' THEN
            SELECT i.is_simulated INTO source_is_synthetic FROM playbook_executions e JOIN incidents i ON i.id=e.incident_id AND i.tenant_id=e.tenant_id WHERE e.id=NEW.resource_id AND e.tenant_id=NEW.tenant_id;
          END IF;
          IF source_is_synthetic THEN NEW.is_synthetic := true; END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER feedback_synthetic_provenance BEFORE INSERT ON feedback_entries FOR EACH ROW EXECUTE FUNCTION enforce_feedback_synthetic_provenance()"
    )
    op.execute(
        "CREATE TRIGGER memory_review_separation BEFORE INSERT ON memory_reviews FOR EACH ROW EXECUTE FUNCTION enforce_memory_review_separation()"
    )
    op.execute(
        """
        CREATE FUNCTION enforce_memory_activation_separation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.to_status = 'ACTIVE' THEN
            IF NEW.actor_user_id IS NULL OR EXISTS (
              SELECT 1 FROM memory_candidate_versions v JOIN memory_candidates c ON c.id=v.candidate_id AND c.tenant_id=v.tenant_id
              WHERE v.id=NEW.version_id AND v.tenant_id=NEW.tenant_id AND c.created_by_user_id=NEW.actor_user_id
            ) THEN RAISE EXCEPTION 'memory author cannot activate own version'; END IF;
            IF NOT EXISTS (SELECT 1 FROM memory_reviews r WHERE r.version_id=NEW.version_id AND r.tenant_id=NEW.tenant_id AND r.decision='APPROVE')
            THEN RAISE EXCEPTION 'approved review required before activation'; END IF;
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER memory_activation_separation BEFORE INSERT ON memory_state_events FOR EACH ROW EXECUTE FUNCTION enforce_memory_activation_separation()"
    )
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY {table}_tenant_isolation ON {table}
            USING (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)"""
        )
        op.execute(f"GRANT SELECT, INSERT ON {table} TO {app_role}")
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM {app_role}")
    op.execute(
        """
        CREATE FUNCTION public.list_due_memory_expirations(p_limit integer)
        RETURNS TABLE (tenant_id uuid, version_id uuid)
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        BEGIN
          IF p_limit < 1 OR p_limit > 500 THEN
            RAISE EXCEPTION 'invalid memory expiration batch size';
          END IF;
          RETURN QUERY
          SELECT v.tenant_id, v.id
          FROM public.memory_candidate_versions v
          JOIN LATERAL (
            SELECT s.to_status
            FROM public.memory_state_events s
            WHERE s.tenant_id = v.tenant_id AND s.version_id = v.id
            ORDER BY s.occurred_at DESC, s.id DESC
            LIMIT 1
          ) latest ON true
          WHERE v.valid_until <= now() AND latest.to_status = 'ACTIVE'
          ORDER BY v.valid_until
          LIMIT p_limit;
        END
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION public.list_due_memory_expirations(integer) FROM PUBLIC")
    op.execute(
        f"GRANT EXECUTE ON FUNCTION public.list_due_memory_expirations(integer) TO {app_role}"
    )
    op.execute(f"GRANT UPDATE (active) ON memory_metric_definitions TO {app_role}")
    op.execute(
        """INSERT INTO permissions (code, description) VALUES
        ('feedback.read','Read tenant feedback'),('feedback.create','Create tenant feedback'),
        ('memory.read','Read tenant governed memory'),('memory.propose','Propose tenant memory'),
        ('memory.review','Review tenant memory'),('memory.activate','Activate tenant memory'),
        ('memory.disable','Disable tenant memory'),('memory.metrics.read','Read tenant memory metrics')
        ON CONFLICT (code) DO NOTHING"""
    )
    op.execute(
        """INSERT INTO role_permissions (tenant_id, role_id, permission_id)
        SELECT r.tenant_id, r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.code='tenant-admin' AND p.code IN ('feedback.read','feedback.create','memory.read','memory.propose','memory.review','memory.activate','memory.disable','memory.metrics.read')
        ON CONFLICT DO NOTHING"""
    )


def downgrade() -> None:
    for table in TABLES:
        op.execute(
            f"""DO $$ BEGIN IF EXISTS (SELECT 1 FROM {table}) THEN
            RAISE EXCEPTION '{table} contains governed history; export it before downgrade'; END IF; END $$"""
        )
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = ANY (ARRAY['feedback.read','feedback.create','memory.read','memory.propose','memory.review','memory.activate','memory.disable','memory.metrics.read']))"
    )
    op.execute(
        "DELETE FROM permissions WHERE code = ANY (ARRAY['feedback.read','feedback.create','memory.read','memory.propose','memory.review','memory.activate','memory.disable','memory.metrics.read'])"
    )
    op.execute("DROP FUNCTION IF EXISTS public.list_due_memory_expirations(integer)")
    op.execute("DROP TRIGGER IF EXISTS feedback_synthetic_provenance ON feedback_entries")
    op.execute("DROP FUNCTION IF EXISTS enforce_feedback_synthetic_provenance()")
    op.execute("DROP TRIGGER memory_activation_separation ON memory_state_events")
    op.execute("DROP FUNCTION enforce_memory_activation_separation()")
    op.execute("DROP TRIGGER memory_review_separation ON memory_reviews")
    op.execute("DROP FUNCTION enforce_memory_review_separation()")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
