import json
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from cyrvanta.modules.integrations.application.finding_ingestion import (
    PersistedFinding,
)
from cyrvanta.modules.integrations.domain.findings import (
    CanonicalEntityReference,
    CanonicalFinding,
    EntityKind,
)


def severity_label(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 40:
        return "medium"
    if score >= 20:
        return "low"
    return "informational"


def _entity_payload(reference: CanonicalEntityReference) -> dict[str, object]:
    return {
        "kind": reference.kind.value,
        "value": reference.value,
        "namespace": reference.namespace,
        "normalized_value": reference.normalized_value,
        "display_value": reference.display_value,
        "attributes": dict(reference.attributes),
    }


def _entity_references(finding: CanonicalFinding) -> list[dict[str, object]]:
    references = [_entity_payload(item) for item in finding.all_entity_references()]
    if finding.source_ip is not None:
        references.append(
            {
                "kind": EntityKind.IP_ADDRESS.value,
                "value": str(finding.source_ip),
                "namespace": "source",
            }
        )
    if finding.destination_ip is not None:
        references.append(
            {
                "kind": EntityKind.IP_ADDRESS.value,
                "value": str(finding.destination_ip),
                "namespace": "destination",
            }
        )
    return references[:32]


class SqlFindingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def persist(self, finding: CanonicalFinding) -> PersistedFinding:
        projection = {
            "id": finding.finding_id,
            "tenant_id": finding.tenant_id,
            "integration_id": finding.integration_id,
            "source": finding.source_system,
            "external_id": finding.source_object_id,
            "observed_at": finding.effective_at,
            "title": finding.title,
            "category": finding.category or "uncategorized",
            "severity": severity_label(finding.severity_score),
            "asset_summary": finding.host.display_value if finding.host else None,
            "identity_summary": finding.user.value if finding.user else None,
            "indicator_summary": (
                str(finding.source_ip) if finding.source_ip is not None else None
            ),
            "raw_reference": finding.evidence_reference.locator,
            "snapshot_sha256": finding.payload_fingerprint,
            "provenance": (
                f"{finding.source_system}:"
                f"{finding.normalization.adapter_version}:"
                f"{finding.normalization.normalizer_version}"
            ),
            "is_simulated": finding.labels.get("simulation") == "true",
        }
        await self._session.execute(
            text(
                """
                INSERT INTO alert_references (
                  id, tenant_id, integration_id, source, external_id,
                  observed_at, title, category, severity, asset_summary,
                  identity_summary, indicator_summary, raw_reference,
                  snapshot_sha256, provenance, is_simulated
                ) VALUES (
                  :id, :tenant_id, :integration_id, :source, :external_id,
                  :observed_at, :title, :category, :severity, :asset_summary,
                  :identity_summary, :indicator_summary, :raw_reference,
                  :snapshot_sha256, :provenance, :is_simulated
                )
                ON CONFLICT DO NOTHING
                """
            ),
            projection,
        )
        finding_id = await self._session.scalar(
            text(
                """
                SELECT id
                FROM alert_references
                WHERE tenant_id = :tenant_id
                  AND integration_id = :integration_id
                  AND source = :source
                  AND external_id = :external_id
                FOR UPDATE
                """
            ),
            projection,
        )
        if not isinstance(finding_id, UUID):
            raise RuntimeError("canonical finding projection could not be claimed")

        duplicate = (
            await self._session.execute(
                text(
                    """
                    SELECT id, revision_number
                    FROM finding_revisions
                    WHERE tenant_id = :tenant_id
                      AND integration_id = :integration_id
                      AND source_object_type = :source_object_type
                      AND source_object_id = :source_object_id
                      AND payload_sha256 = :payload_sha256
                    """
                ),
                {
                    "tenant_id": finding.tenant_id,
                    "integration_id": finding.integration_id,
                    "source_object_type": finding.source_object_type,
                    "source_object_id": finding.source_object_id,
                    "payload_sha256": finding.payload_fingerprint,
                },
            )
        ).one_or_none()
        if duplicate is not None:
            return PersistedFinding(
                finding_id=finding_id,
                revision_id=duplicate.id,
                revision_number=duplicate.revision_number,
                created=False,
            )

        revision_number = await self._session.scalar(
            text(
                """
                    SELECT COALESCE(max(revision_number), 0) + 1
                    FROM finding_revisions
                    WHERE tenant_id = :tenant_id
                      AND alert_reference_id = :finding_id
                    """
            ),
            {"tenant_id": finding.tenant_id, "finding_id": finding_id},
        )
        if not isinstance(revision_number, int):
            raise RuntimeError("canonical finding revision number is invalid")
        revision_id = uuid4()
        await self._session.execute(
            text(
                """
                INSERT INTO finding_revisions (
                  id, tenant_id, alert_reference_id, revision_number,
                  integration_id, source_system, source_instance_id,
                  source_object_type, source_object_id, source_occurred_at,
                  observed_at, effective_at, effective_time_basis, title,
                  description, severity_score, confidence, category,
                  external_status, rule_reference, entity_references,
                  evidence_locator, payload_sha256, fingerprint_mode,
                  fingerprint_version, adapter_name, adapter_version,
                  normalizer_version, canonical_schema_version,
                  normalization_status, completeness_score, issue_codes
                ) VALUES (
                  :id, :tenant_id, :alert_reference_id, :revision_number,
                  :integration_id, :source_system, :source_instance_id,
                  :source_object_type, :source_object_id, :source_occurred_at,
                  :observed_at, :effective_at, :effective_time_basis, :title,
                  :description, :severity_score, :confidence, :category,
                  :external_status, :rule_reference,
                  CAST(:entity_references AS jsonb), :evidence_locator,
                  :payload_sha256, :fingerprint_mode, :fingerprint_version,
                  :adapter_name, :adapter_version, :normalizer_version,
                  :canonical_schema_version, :normalization_status,
                  :completeness_score, :issue_codes
                )
                """
            ),
            {
                "id": revision_id,
                "tenant_id": finding.tenant_id,
                "alert_reference_id": finding_id,
                "revision_number": revision_number,
                "integration_id": finding.integration_id,
                "source_system": finding.source_system,
                "source_instance_id": finding.source_instance_id,
                "source_object_type": finding.source_object_type,
                "source_object_id": finding.source_object_id,
                "source_occurred_at": finding.source_occurred_at,
                "observed_at": finding.observed_at,
                "effective_at": finding.effective_at,
                "effective_time_basis": finding.effective_time_basis.value,
                "title": finding.title,
                "description": finding.description,
                "severity_score": finding.severity_score,
                "confidence": finding.confidence,
                "category": finding.category,
                "external_status": finding.status,
                "rule_reference": finding.rule_reference,
                "entity_references": json.dumps(
                    _entity_references(finding),
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                "evidence_locator": finding.evidence_reference.locator,
                "payload_sha256": finding.payload_fingerprint,
                "fingerprint_mode": finding.normalization.fingerprint_mode.value,
                "fingerprint_version": finding.normalization.fingerprint_version,
                "adapter_name": finding.normalization.adapter_name,
                "adapter_version": finding.normalization.adapter_version,
                "normalizer_version": finding.normalization.normalizer_version,
                "canonical_schema_version": finding.schema_version,
                "normalization_status": finding.normalization.status.value,
                "completeness_score": finding.normalization.completeness_score,
                "issue_codes": list(finding.normalization.issue_codes),
            },
        )
        await self._session.execute(
            text(
                """
                UPDATE alert_references
                SET
                  current_revision_id = :revision_id,
                  current_revision_number = :revision_number,
                  observed_at = :observed_at,
                  title = :title,
                  category = :category,
                  severity = :severity,
                  asset_summary = :asset_summary,
                  identity_summary = :identity_summary,
                  indicator_summary = :indicator_summary,
                  raw_reference = :raw_reference,
                  snapshot_sha256 = :snapshot_sha256,
                  provenance = :provenance,
                  updated_at = now()
                WHERE id = :id AND tenant_id = :tenant_id
                """
            ),
            {
                **projection,
                "revision_id": revision_id,
                "revision_number": revision_number,
            },
        )
        return PersistedFinding(
            finding_id=finding_id,
            revision_id=revision_id,
            revision_number=revision_number,
            created=True,
        )
