from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from uuid import NAMESPACE_URL, UUID, uuid5

from cyrvanta.modules.correlation.application.schemas import CanonicalDemoResponse
from cyrvanta.modules.correlation.domain.models import bucket_bounds
from cyrvanta.modules.integrations.application.finding_ingestion import (
    FindingIngestionService,
)
from cyrvanta.modules.integrations.domain.findings import (
    CanonicalFinding,
    EffectiveTimeBasis,
    ExternalEvidenceReference,
    FingerprintMode,
    NormalizationAssessment,
    NormalizationStatus,
    canonical_payload_sha256,
)
from cyrvanta.modules.integrations.infrastructure.finding_repository import (
    SqlFindingRepository,
)
from cyrvanta.shared.config import get_settings
from cyrvanta.shared.database import SessionFactory, tenant_session
from cyrvanta.shared.infrastructure.event_store import SqlEventStore


class CanonicalCorrelationDemo:
    async def generate(
        self, tenant_id: UUID, correlation_id: UUID
    ) -> CanonicalDemoResponse:
        settings = get_settings()
        event_store = SqlEventStore(SessionFactory, settings.event_max_payload_bytes)
        now = datetime.now(UTC)
        current_bucket_start, _bucket_end = bucket_bounds(now)
        bucket_start = current_bucket_start - timedelta(minutes=10)
        integration_id = uuid5(NAMESPACE_URL, f"cyrvanta:{tenant_id}:demo-v2")
        definitions = (
            ("auth-failure", "demo-auth-failure", "Repeated authentication failures", 52, 1),
            ("auth-success", "demo-auth-success", "Atypical authentication success", 68, 3),
            ("privilege-change", "demo-privilege-change", "Privilege change observed", 74, 5),
            ("resource-access", "demo-resource-access", "Protected resource access", 86, 7),
        )
        created = 0
        duplicates = 0
        async with tenant_session(tenant_id) as session:
            ingestion = FindingIngestionService(
                SqlFindingRepository(session),
                event_store.recorder(session),
            )
            for code, rule_reference, title, severity, minute in definitions:
                effective_at = bucket_start + timedelta(minutes=minute)
                material = {
                    "scenario": "credential-attack-v2",
                    "bucket": bucket_start.isoformat(),
                    "signal": code,
                    "source_ip": "192.0.2.44",
                }
                fingerprint = canonical_payload_sha256(material)
                object_id = (
                    f"credential-attack-v2-"
                    f"{bucket_start.strftime('%Y%m%dT%H%MZ')}-{code}"
                )
                finding = CanonicalFinding(
                    finding_id=uuid5(
                        NAMESPACE_URL,
                        f"cyrvanta:{tenant_id}:demo-v2:{object_id}",
                    ),
                    tenant_id=tenant_id,
                    integration_id=integration_id,
                    source_system="cyrvanta-demo-v2",
                    source_instance_id=integration_id,
                    source_object_type="finding",
                    source_object_id=object_id,
                    source_occurred_at=effective_at,
                    observed_at=now,
                    effective_at=effective_at,
                    effective_time_basis=EffectiveTimeBasis.SOURCE,
                    title=title,
                    description="Synthetic canonical fixture for deterministic correlation.",
                    severity_score=severity,
                    confidence=None,
                    category="credential-access",
                    status="new",
                    rule_reference=rule_reference,
                    source_ip=ip_address("192.0.2.44"),
                    evidence_reference=ExternalEvidenceReference(
                        source_system="cyrvanta-demo-v2",
                        source_instance_id=integration_id,
                        source_object_type="finding",
                        source_object_id=object_id,
                        source_timestamp=effective_at,
                        locator=f"cyrvanta://demo/credential-attack-v2/{object_id}",
                        adapter_version="1.0",
                        normalizer_version="1.0",
                        payload_sha256=fingerprint,
                    ),
                    payload_fingerprint=fingerprint,
                    normalization=NormalizationAssessment(
                        status=NormalizationStatus.VALID,
                        completeness_score=100,
                        issue_codes=(),
                        adapter_name="cyrvanta-demo",
                        adapter_version="1.0",
                        normalizer_version="1.0",
                        fingerprint_mode=FingerprintMode.ADAPTER_MATERIAL,
                    ),
                    labels={"simulation": "true"},
                    schema_version=1,
                )
                result = await ingestion.ingest(
                    finding, correlation_id=correlation_id
                )
                if result.created:
                    created += 1
                else:
                    duplicates += 1
        return CanonicalDemoResponse(
            scenario="credential-attack-v2",
            findings_created=created,
            duplicates=duplicates,
            correlation_queued=created > 0,
            correlation_id=correlation_id,
        )
