import json
from datetime import UTC, datetime
from hashlib import sha256
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from cyrvanta.modules.integrations.domain.errors import (
    ConnectorError,
    ConnectorErrorCode,
)
from cyrvanta.modules.integrations.domain.models import (
    CanonicalEntityReference,
    CanonicalFinding,
    ExternalEvidenceReference,
)
from cyrvanta.modules.integrations.infrastructure.wazuh.schemas import WazuhHit

NORMALIZER_VERSION = "1.0"
CANONICAL_PAYLOAD_VERSION = "1.0"


def _nested(payload: dict[str, Any], *path: str) -> Any:
    current: Any = payload
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        return datetime.now(UTC)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    except ValueError:
        return datetime.now(UTC)


def _ip(value: Any) -> IPv4Address | IPv6Address | None:
    if not isinstance(value, str):
        return None
    try:
        return ip_address(value)
    except ValueError:
        return None


class WazuhNormalizer:
    def normalize(
        self, hit: WazuhHit, tenant_id: UUID, source_instance_id: UUID
    ) -> CanonicalFinding:
        source = hit.source
        try:
            canonical_json = json.dumps(
                source, sort_keys=True, separators=(",", ":"), default=str
            ).encode()
            payload_hash = sha256(canonical_json).hexdigest()
            occurred_at = _timestamp(source.get("timestamp"))
            rule_level = _nested(source, "rule", "level")
            severity = min(100, max(0, int(rule_level or 0) * 7))
            title_value = _nested(source, "rule", "description")
            title = str(title_value or "Unclassified security finding")[:500]
            groups = _nested(source, "rule", "groups")
            category = str(groups[0])[:120] if isinstance(groups, list) and groups else None
            agent_name = _nested(source, "agent", "name")
            user_name = (
                _nested(source, "data", "win", "eventdata", "targetUserName")
                or _nested(source, "data", "srcuser")
            )
            source_ip = _ip(
                _nested(source, "data", "srcip")
                or _nested(source, "data", "win", "eventdata", "ipAddress")
            )
            destination_ip = _ip(_nested(source, "data", "dstip"))
            rule_id = _nested(source, "rule", "id")
            locator = f"opensearch://{hit.index}/{hit.document_id}"
            return CanonicalFinding(
                id=uuid5(
                    NAMESPACE_URL,
                    f"cyrvanta:wazuh:{source_instance_id}:{hit.document_id}",
                ),
                tenant_id=tenant_id,
                source_system="wazuh",
                source_instance_id=source_instance_id,
                source_object_type="alert",
                source_object_id=hit.document_id,
                occurred_at=occurred_at,
                ingested_at=datetime.now(UTC),
                title=title,
                description=None,
                severity=severity,
                confidence=None,
                category=category,
                status="new",
                rule_reference=str(rule_id) if rule_id is not None else None,
                host=(
                    CanonicalEntityReference(
                        entity_type="host", value=str(agent_name), display_name=str(agent_name)
                    )
                    if agent_name
                    else None
                ),
                user=(
                    CanonicalEntityReference(entity_type="user", value=str(user_name))
                    if user_name
                    else None
                ),
                source_ip=source_ip,
                destination_ip=destination_ip,
                labels={"adapter": "wazuh"},
                raw_reference=ExternalEvidenceReference(
                    source_system="wazuh",
                    source_instance_id=source_instance_id,
                    source_object_type="alert",
                    source_object_id=hit.document_id,
                    source_timestamp=occurred_at,
                    locator=locator,
                    adapter_version="1.0",
                    normalizer_version=NORMALIZER_VERSION,
                    payload_sha256=payload_hash,
                ),
                normalized_payload_version=CANONICAL_PAYLOAD_VERSION,
            )
        except (TypeError, ValueError) as exc:
            raise ConnectorError(
                ConnectorErrorCode.SOURCE_SCHEMA_CHANGED,
                "Source alert could not be normalized",
            ) from exc
