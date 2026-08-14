# ruff: noqa: E501, S608
"""Seed default stack integrations (Wazuh, OpenSearch, n8n) idempotently for tenants."""

import json
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

from cyrvanta.modules.integrations.application.connection_service import (
    CURRENT_CONFIGURATION_SCHEMA_VERSION,
)
from cyrvanta.modules.directory.application.crypto import SecretCipher
from cyrvanta.shared.config import get_settings

revision = "0023_default_integrations"
down_revision = "0022_decision_expiration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    settings = get_settings()
    cipher = SecretCipher(settings.integration_encryption_key)
    bind = op.get_bind()

    tenants = bind.execute(sa.text("SELECT id, slug FROM tenants")).fetchall()

    for row in tenants:
        tenant_id = row[0]
        existing = bind.execute(
            sa.text("SELECT connector_type FROM integrations WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        ).fetchall()
        existing_types = {r[0] for r in existing}

        # 1. Wazuh Manager
        if "WAZUH" not in existing_types:
            wazuh_config = {
                "base_url": "https://wazuh-manager:55000",
                "username": "wazuh-api",
                "password": "SecretWazuhPassword123!",
                "timeout_seconds": 10,
            }
            enc = cipher.encrypt(json.dumps(wazuh_config, separators=(",", ":"), sort_keys=True))
            bind.execute(
                sa.text(
                    """
                    INSERT INTO integrations (
                        id, tenant_id, connector_type, name, status,
                        configuration_schema_version, configuration_encrypted,
                        capabilities_snapshot, created_at, updated_at
                    ) VALUES (
                        :id, :tenant_id, :connector_type, :name, :status,
                        :version, :encrypted, :capabilities, now(), now()
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "tenant_id": tenant_id,
                    "connector_type": "WAZUH",
                    "name": "Wazuh SIEM Local Manager",
                    "status": "active",
                    "version": CURRENT_CONFIGURATION_SCHEMA_VERSION,
                    "encrypted": enc.encode(),
                    "capabilities": json.dumps({"capabilities": ["findings.ingest"]}),
                },
            )

        # 2. OpenSearch
        if "OPENSEARCH" not in existing_types:
            os_config = {"base_url": "http://opensearch:9200", "timeout_seconds": 10}
            enc = cipher.encrypt(json.dumps(os_config, separators=(",", ":"), sort_keys=True))
            bind.execute(
                sa.text(
                    """
                    INSERT INTO integrations (
                        id, tenant_id, connector_type, name, status,
                        configuration_schema_version, configuration_encrypted,
                        capabilities_snapshot, created_at, updated_at
                    ) VALUES (
                        :id, :tenant_id, :connector_type, :name, :status,
                        :version, :encrypted, :capabilities, now(), now()
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "tenant_id": tenant_id,
                    "connector_type": "OPENSEARCH",
                    "name": "OpenSearch Telemetry Cluster",
                    "status": "active",
                    "version": CURRENT_CONFIGURATION_SCHEMA_VERSION,
                    "encrypted": enc.encode(),
                    "capabilities": json.dumps({"capabilities": ["telemetry.search"]}),
                },
            )

        # 3. n8n
        if "N8N" not in existing_types:
            n8n_config = {
                "base_url": "http://n8n:5678",
                "api_key": "n8n_api_key_local_demo_12345",
                "timeout_seconds": 10,
            }
            enc = cipher.encrypt(json.dumps(n8n_config, separators=(",", ":"), sort_keys=True))
            bind.execute(
                sa.text(
                    """
                    INSERT INTO integrations (
                        id, tenant_id, connector_type, name, status,
                        configuration_schema_version, configuration_encrypted,
                        capabilities_snapshot, created_at, updated_at
                    ) VALUES (
                        :id, :tenant_id, :connector_type, :name, :status,
                        :version, :encrypted, :capabilities, now(), now()
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "tenant_id": tenant_id,
                    "connector_type": "N8N",
                    "name": "n8n SOAR Automation Engine",
                    "status": "active",
                    "version": CURRENT_CONFIGURATION_SCHEMA_VERSION,
                    "encrypted": enc.encode(),
                    "capabilities": json.dumps({"capabilities": ["playbook.dispatch"]}),
                },
            )


def downgrade() -> None:
    pass
