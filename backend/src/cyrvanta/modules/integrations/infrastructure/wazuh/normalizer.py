from collections.abc import Callable
from datetime import UTC, datetime
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from cyrvanta.modules.integrations.domain.errors import (
    ConnectorError,
    ConnectorErrorCode,
)
from cyrvanta.modules.integrations.domain.findings import (
    CanonicalEntityReference,
    CanonicalFinding,
    EffectiveTimeBasis,
    EntityKind,
    ExternalEvidenceReference,
    FingerprintMode,
    NormalizationAssessment,
    NormalizationStatus,
    canonical_payload_sha256,
)
from cyrvanta.modules.integrations.infrastructure.wazuh.schemas import WazuhHit

ADAPTER_VERSION = "1.0"
NORMALIZER_VERSION = "2.0"
CANONICAL_SCHEMA_VERSION = 1


def _nested(payload: dict[str, Any], *path: str) -> Any:
    current: Any = payload
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def _ip(value: Any) -> IPv4Address | IPv6Address | None:
    if not isinstance(value, str):
        return None
    try:
        return ip_address(value)
    except ValueError:
        return None


class WazuhNormalizer:
    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def normalize(
        self, hit: WazuhHit, tenant_id: UUID, source_instance_id: UUID
    ) -> CanonicalFinding:
        source = hit.source
        try:
            payload_hash = canonical_payload_sha256(source)
            observed_at = self._clock().astimezone(UTC)
            source_occurred_at = _timestamp(source.get("timestamp"))
            effective_at = source_occurred_at or observed_at
            effective_time_basis = (
                EffectiveTimeBasis.SOURCE
                if source_occurred_at is not None
                else EffectiveTimeBasis.INGESTED
            )
            rule_level = _nested(source, "rule", "level")
            severity = min(100, max(0, int(rule_level or 0) * 7))
            title_value = _nested(source, "rule", "description")
            title = str(title_value or "Unclassified security finding")[:500]
            groups = _nested(source, "rule", "groups")
            category = str(groups[0])[:120] if isinstance(groups, list) and groups else None
            agent_name = _nested(source, "agent", "name")
            user_name = _nested(source, "data", "win", "eventdata", "targetUserName") or _nested(
                source, "data", "srcuser"
            )
            source_ip = _ip(
                _nested(source, "data", "srcip")
                or _nested(source, "data", "win", "eventdata", "ipAddress")
            )
            destination_ip = _ip(_nested(source, "data", "dstip"))
            rule_id = _nested(source, "rule", "id")
            locator = f"opensearch://{hit.index}/{hit.document_id}"
            issue_codes: list[str] = []
            completeness_dimensions = 5
            complete_dimensions = 0
            if source_occurred_at is not None:
                complete_dimensions += 1
            else:
                issue_codes.append("source_timestamp_missing_or_invalid")
            if rule_id is not None:
                complete_dimensions += 1
            else:
                issue_codes.append("rule_reference_missing")
            if title_value:
                complete_dimensions += 1
            else:
                issue_codes.append("title_fallback_used")
            if category is not None:
                complete_dimensions += 1
            else:
                issue_codes.append("category_missing")
            if agent_name or source_ip is not None or destination_ip is not None:
                complete_dimensions += 1
            else:
                issue_codes.append("entity_reference_missing")
            assessment = NormalizationAssessment(
                status=(
                    NormalizationStatus.VALID if not issue_codes else NormalizationStatus.PARTIAL
                ),
                completeness_score=round(complete_dimensions * 100 / completeness_dimensions),
                issue_codes=tuple(issue_codes),
                adapter_name="wazuh",
                adapter_version=ADAPTER_VERSION,
                normalizer_version=NORMALIZER_VERSION,
                fingerprint_mode=FingerprintMode.RAW_DOCUMENT,
                canonical_schema_version=CANONICAL_SCHEMA_VERSION,
            )
            return CanonicalFinding(
                finding_id=uuid5(
                    NAMESPACE_URL,
                    f"cyrvanta:wazuh:{source_instance_id}:{hit.document_id}",
                ),
                tenant_id=tenant_id,
                integration_id=source_instance_id,
                source_system="wazuh",
                source_instance_id=source_instance_id,
                source_object_type="alert",
                source_object_id=hit.document_id,
                source_occurred_at=source_occurred_at,
                observed_at=observed_at,
                effective_at=effective_at,
                effective_time_basis=effective_time_basis,
                title=title,
                description=None,
                severity_score=severity,
                confidence=None,
                category=category,
                status="new",
                rule_reference=str(rule_id) if rule_id is not None else None,
                host=(
                    CanonicalEntityReference(
                        kind=EntityKind.ASSET,
                        value=str(agent_name),
                        display_value=str(agent_name),
                        namespace="wazuh-agent",
                    )
                    if agent_name
                    else None
                ),
                user=(
                    CanonicalEntityReference(
                        kind=EntityKind.ACCOUNT,
                        value=str(user_name),
                        namespace="wazuh-user",
                    )
                    if user_name
                    else None
                ),
                source_ip=source_ip,
                destination_ip=destination_ip,
                labels={"adapter": "wazuh"},
                evidence_reference=ExternalEvidenceReference(
                    source_system="wazuh",
                    source_instance_id=source_instance_id,
                    source_object_type="alert",
                    source_object_id=hit.document_id,
                    source_timestamp=source_occurred_at,
                    locator=locator,
                    adapter_version=ADAPTER_VERSION,
                    normalizer_version=NORMALIZER_VERSION,
                    payload_sha256=payload_hash,
                ),
                payload_fingerprint=payload_hash,
                normalization=assessment,
                schema_version=CANONICAL_SCHEMA_VERSION,
            )
        except (TypeError, ValueError) as exc:
            raise ConnectorError(
                ConnectorErrorCode.SOURCE_SCHEMA_CHANGED,
                "Source alert could not be normalized",
            ) from exc
