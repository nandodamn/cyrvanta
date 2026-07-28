"""Add tenant-isolated event outbox and inbox delivery state."""

import os
import re

from alembic import op

revision = "0008_event_delivery"
down_revision = "0007_playbooks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    app_role = os.environ.get("POSTGRES_APP_USER", "cyrvanta_app")
    if re.fullmatch(r"[a-z_][a-z0-9_]*", app_role) is None:
        raise ValueError("POSTGRES_APP_USER is not a safe PostgreSQL identifier")

    op.execute(
        """
        CREATE TABLE event_outbox (
          event_id uuid PRIMARY KEY,
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          event_name varchar(160) NOT NULL,
          schema_version integer NOT NULL CHECK (schema_version > 0),
          aggregate_type varchar(100) NOT NULL,
          aggregate_id uuid NOT NULL,
          occurred_at timestamptz NOT NULL,
          correlation_id uuid NOT NULL,
          causation_id uuid,
          producer varchar(120) NOT NULL,
          payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
          status varchar(24) NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending', 'publishing', 'published')),
          attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
          available_at timestamptz NOT NULL DEFAULT now(),
          lease_token uuid,
          lease_expires_at timestamptz,
          published_at timestamptz,
          last_error_code varchar(80),
          created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE event_inbox (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          event_id uuid NOT NULL,
          consumer_name varchar(120) NOT NULL,
          event_name varchar(160) NOT NULL,
          schema_version integer NOT NULL CHECK (schema_version > 0),
          status varchar(24) NOT NULL
            CHECK (status IN ('processing', 'completed', 'failed')),
          attempt_count integer NOT NULL DEFAULT 1 CHECK (attempt_count >= 1),
          lease_expires_at timestamptz,
          first_received_at timestamptz NOT NULL DEFAULT now(),
          last_received_at timestamptz NOT NULL DEFAULT now(),
          completed_at timestamptz,
          last_error_code varchar(80),
          UNIQUE (tenant_id, consumer_name, event_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_event_outbox_dispatch
          ON event_outbox(status, available_at, created_at)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_event_outbox_aggregate
          ON event_outbox(tenant_id, aggregate_type, aggregate_id, occurred_at)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_event_outbox_correlation
          ON event_outbox(tenant_id, correlation_id, occurred_at)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_event_inbox_consumer_time
          ON event_inbox(tenant_id, consumer_name, last_received_at DESC)
        """
    )

    for table in ("event_outbox", "event_inbox"):
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
        CREATE FUNCTION public.claim_event_outbox(
          p_batch_size integer,
          p_lease_seconds integer
        )
        RETURNS TABLE (
          event_id uuid,
          tenant_id uuid,
          event_name varchar,
          schema_version integer,
          aggregate_type varchar,
          aggregate_id uuid,
          occurred_at timestamptz,
          correlation_id uuid,
          causation_id uuid,
          producer varchar,
          payload jsonb,
          lease_token uuid
        )
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        BEGIN
          IF p_batch_size < 1 OR p_batch_size > 500 THEN
            RAISE EXCEPTION 'invalid outbox batch size';
          END IF;
          IF p_lease_seconds < 1 OR p_lease_seconds > 3600 THEN
            RAISE EXCEPTION 'invalid outbox lease';
          END IF;
          RETURN QUERY
          WITH candidates AS (
            SELECT o.event_id
            FROM public.event_outbox AS o
            WHERE
              (o.status = 'pending' AND o.available_at <= now())
              OR
              (o.status = 'publishing' AND o.lease_expires_at < now())
            ORDER BY o.created_at
            FOR UPDATE SKIP LOCKED
            LIMIT p_batch_size
          )
          UPDATE public.event_outbox AS o
          SET
            status = 'publishing',
            attempt_count = o.attempt_count + 1,
            lease_token = gen_random_uuid(),
            lease_expires_at = now() + make_interval(secs => p_lease_seconds),
            last_error_code = NULL
          FROM candidates AS c
          WHERE o.event_id = c.event_id
          RETURNING
            o.event_id,
            o.tenant_id,
            o.event_name,
            o.schema_version,
            o.aggregate_type,
            o.aggregate_id,
            o.occurred_at,
            o.correlation_id,
            o.causation_id,
            o.producer,
            o.payload,
            o.lease_token;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.confirm_event_outbox(
          p_event_id uuid,
          p_lease_token uuid
        )
        RETURNS boolean
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          UPDATE public.event_outbox
          SET
            status = 'published',
            published_at = now(),
            lease_token = NULL,
            lease_expires_at = NULL,
            last_error_code = NULL
          WHERE event_id = p_event_id
            AND status = 'publishing'
            AND lease_token = p_lease_token
          RETURNING true
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.fail_event_outbox(
          p_event_id uuid,
          p_lease_token uuid,
          p_error_code varchar,
          p_retry_seconds integer
        )
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        BEGIN
          IF p_retry_seconds < 1 OR p_retry_seconds > 3600 THEN
            RAISE EXCEPTION 'invalid outbox retry';
          END IF;
          IF p_error_code !~ '^[a-z0-9_]{1,80}$' THEN
            RAISE EXCEPTION 'invalid outbox error code';
          END IF;
          RETURN (
            WITH updated AS (
              UPDATE public.event_outbox
              SET
                status = 'pending',
                available_at = now() + make_interval(secs => p_retry_seconds),
                lease_token = NULL,
                lease_expires_at = NULL,
                last_error_code = p_error_code
              WHERE event_id = p_event_id
                AND status = 'publishing'
                AND lease_token = p_lease_token
              RETURNING 1
            )
            SELECT EXISTS (SELECT 1 FROM updated)
          );
        END
        $$
        """
    )

    for function in (
        "claim_event_outbox(integer, integer)",
        "confirm_event_outbox(uuid, uuid)",
        "fail_event_outbox(uuid, uuid, varchar, integer)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION public.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION public.{function} TO {app_role}")

    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON event_outbox, event_inbox TO {app_role}")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM event_outbox)
             OR EXISTS (SELECT 1 FROM event_inbox) THEN
            RAISE EXCEPTION
              'event delivery tables are not empty; drain and back up before downgrade';
          END IF;
        END
        $$
        """
    )
    op.execute("DROP FUNCTION public.fail_event_outbox(uuid, uuid, varchar, integer)")
    op.execute("DROP FUNCTION public.confirm_event_outbox(uuid, uuid)")
    op.execute("DROP FUNCTION public.claim_event_outbox(integer, integer)")
    op.execute("DROP TABLE event_inbox")
    op.execute("DROP TABLE event_outbox")
