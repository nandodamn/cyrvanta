# ruff: noqa: E501, S608
"""Add privileged discovery functions for durable decision expiration."""

import os

from alembic import op

revision = "0022_decision_expiration"
down_revision = "0021_alert_triage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    app_role = os.getenv("CYRVANTA_DB_APP_ROLE", "cyrvanta_app")
    op.execute(
        """
        CREATE FUNCTION public.list_due_approval_request_expirations(p_limit integer)
        RETURNS TABLE (tenant_id uuid, approval_request_id uuid)
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        BEGIN
          IF p_limit < 1 OR p_limit > 500 THEN
            RAISE EXCEPTION 'invalid approval expiration batch size';
          END IF;
          RETURN QUERY
          SELECT r.tenant_id, r.id
          FROM public.approval_requests r
          JOIN public.action_proposals p
            ON p.tenant_id = r.tenant_id AND p.id = r.proposal_id
          WHERE r.status = 'PENDING' AND r.expires_at <= now()
            AND p.is_simulated = false
          ORDER BY r.expires_at, r.id
          LIMIT p_limit;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.list_due_authorization_expirations(p_limit integer)
        RETURNS TABLE (tenant_id uuid, authorization_id uuid)
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        BEGIN
          IF p_limit < 1 OR p_limit > 500 THEN
            RAISE EXCEPTION 'invalid authorization expiration batch size';
          END IF;
          RETURN QUERY
          SELECT a.tenant_id, a.id
          FROM public.action_authorizations a
          JOIN public.action_proposals p
            ON p.tenant_id = a.tenant_id AND p.id = a.proposal_id
          WHERE a.status = 'ACTIVE' AND a.expires_at <= now()
            AND p.is_simulated = false
          ORDER BY a.expires_at, a.id
          LIMIT p_limit;
        END
        $$
        """
    )
    for function_name in (
        "list_due_approval_request_expirations",
        "list_due_authorization_expirations",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION public.{function_name}(integer) FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION public.{function_name}(integer) TO {app_role}")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.list_due_authorization_expirations(integer)")
    op.execute("DROP FUNCTION IF EXISTS public.list_due_approval_request_expirations(integer)")
