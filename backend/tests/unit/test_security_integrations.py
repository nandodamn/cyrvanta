import ast
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from cyrvanta.modules.integrations.application.finding_ingestion import (
    FINDING_NORMALIZED_EVENT,
    FindingIngestionService,
    PersistedFinding,
)
from cyrvanta.modules.integrations.application.services.synchronization import (
    FindingSynchronizationService,
    finding_idempotency_key,
)
from cyrvanta.modules.integrations.domain.errors import (
    ConnectorError,
    ConnectorErrorCode,
    UnsupportedCapabilityError,
)
from cyrvanta.modules.integrations.domain.findings import (
    EffectiveTimeBasis,
    FingerprintMode,
    NormalizationAssessment,
    NormalizationStatus,
    canonical_payload_sha256,
)
from cyrvanta.modules.integrations.domain.models import (
    CanonicalFinding,
    ConnectorConfiguration,
    ExternalEvidenceReference,
)
from cyrvanta.modules.integrations.infrastructure.composition import (
    production_connector_registry,
)
from cyrvanta.modules.integrations.infrastructure.registry.connector_registry import (
    ConnectorRegistry,
)
from cyrvanta.modules.integrations.infrastructure.wazuh.client import WazuhIndexerClient
from cyrvanta.modules.integrations.infrastructure.wazuh.config import (
    WazuhConnectorConfigV1,
)
from cyrvanta.modules.integrations.infrastructure.wazuh.normalizer import WazuhNormalizer
from cyrvanta.modules.integrations.infrastructure.wazuh.schemas import WazuhHit
from cyrvanta.modules.integrations.testing.fake_connector import FakeSIEMConnector
from cyrvanta.shared.domain.events import DomainEvent


def finding(
    tenant_id: UUID,
    source_id: str = "alert-1",
    integration_id: UUID | None = None,
) -> CanonicalFinding:
    now = datetime.now(UTC)
    source_instance_id = integration_id or uuid4()
    payload_hash = canonical_payload_sha256({"source_id": source_id})
    return CanonicalFinding(
        finding_id=uuid4(),
        tenant_id=tenant_id,
        integration_id=source_instance_id,
        source_system="test",
        source_instance_id=source_instance_id,
        source_object_type="finding",
        source_object_id=source_id,
        source_occurred_at=now,
        observed_at=now,
        effective_at=now,
        effective_time_basis=EffectiveTimeBasis.SOURCE,
        title="Test finding",
        severity_score=50,
        status="new",
        evidence_reference=ExternalEvidenceReference(
            source_system="test",
            source_instance_id=source_instance_id,
            source_object_type="finding",
            source_object_id=source_id,
            source_timestamp=now,
            locator=f"test://{source_id}",
            adapter_version="1",
            normalizer_version="1",
            payload_sha256=payload_hash,
        ),
        payload_fingerprint=payload_hash,
        normalization=NormalizationAssessment(
            status=NormalizationStatus.VALID,
            completeness_score=100,
            issue_codes=(),
            adapter_name="test",
            adapter_version="1",
            normalizer_version="1",
            fingerprint_mode=FingerprintMode.ADAPTER_MATERIAL,
        ),
    )


def configuration(tenant_id: UUID) -> ConnectorConfiguration:
    return ConnectorConfiguration(
        integration_id=uuid4(),
        tenant_id=tenant_id,
        connector_type="wazuh",
        schema_version="1",
        values={
            "manager_host": "wazuh-manager",
            "manager_port": 1514,
            "indexer_url": "http://opensearch:9200",
            "index_pattern": "wazuh-alerts-*",
            "verify_tls": False,
        },
    )


def test_registry_resolves_only_registered_wazuh_connector() -> None:
    tenant_id = uuid4()
    registry = production_connector_registry()
    connector = registry.create("wazuh", configuration(tenant_id))
    assert type(connector).__name__ == "WazuhSIEMAdapter"
    assert registry.registered_types() == ("wazuh",)


def test_unregistered_connector_fails_with_canonical_error() -> None:
    tenant_id = uuid4()
    config = configuration(tenant_id).model_copy(update={"connector_type": "qradar"})
    with pytest.raises(ConnectorError) as captured:
        ConnectorRegistry().create("qradar", config)
    assert captured.value.code == ConnectorErrorCode.INVALID_CONFIGURATION


def test_new_connector_registration_does_not_change_domain() -> None:
    registry = ConnectorRegistry()
    tenant_id = uuid4()
    fake = FakeSIEMConnector()
    registry.register("test-only", lambda config: fake)
    config = configuration(tenant_id).model_copy(update={"connector_type": "test-only"})
    assert registry.create("test-only", config) is fake


async def test_unsupported_capability_is_explicit() -> None:
    with pytest.raises(UnsupportedCapabilityError) as captured:
        await FakeSIEMConnector().fetch_incidents(uuid4(), None, None, None, 10)
    assert captured.value.code == ConnectorErrorCode.UNSUPPORTED_CAPABILITY


async def test_synchronization_preserves_tenant_and_deduplicates_batch() -> None:
    tenant_id = uuid4()
    integration_id = uuid4()
    item = finding(tenant_id, integration_id=integration_id)
    connector = FakeSIEMConnector(findings=[item, item])
    received: list[tuple[CanonicalFinding, str]] = []

    async def sink(value: CanonicalFinding, key: str) -> None:
        received.append((value, key))

    batch = await FindingSynchronizationService(connector, sink).synchronize(
        tenant_id, integration_id
    )
    assert len(batch.items) == 2
    assert len(received) == 1
    assert received[0][0].tenant_id == tenant_id
    assert received[0][1] == finding_idempotency_key(integration_id, item)


async def test_synchronization_rejects_cross_tenant_output() -> None:
    requested_tenant = uuid4()
    malicious_tenant = uuid4()

    class UnsafeFake(FakeSIEMConnector):
        async def fetch_findings(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
            from cyrvanta.modules.integrations.domain.models import FindingBatch

            return FindingBatch(items=[finding(malicious_tenant)])

    async def sink(value: CanonicalFinding, key: str) -> None:
        raise AssertionError("Cross-tenant finding must not reach the sink")

    with pytest.raises(ValueError, match="tenant scope"):
        await FindingSynchronizationService(UnsafeFake(), sink).synchronize(
            requested_tenant, uuid4()
        )


def test_wazuh_normalizer_maps_known_and_unknown_payloads() -> None:
    tenant_id = uuid4()
    source_id = uuid4()
    normalizer = WazuhNormalizer()
    known = WazuhHit.model_validate(
        {
            "_index": "wazuh-alerts-4.x-2026.07.28",
            "_id": "abc",
            "_source": {
                "timestamp": "2026-07-28T12:00:00Z",
                "rule": {
                    "id": "60602",
                    "level": 9,
                    "description": "Application warning event",
                    "groups": ["windows"],
                },
                "agent": {"name": "CYRVANTA-WINDOWS-LAB"},
                "data": {"srcip": "192.0.2.10"},
            },
        }
    )
    mapped = normalizer.normalize(known, tenant_id, source_id)
    assert mapped.tenant_id == tenant_id
    assert mapped.source_system == "wazuh"
    assert mapped.rule_reference == "60602"
    assert mapped.severity == 63
    assert str(mapped.source_ip) == "192.0.2.10"
    unknown = WazuhHit.model_validate(
        {"_index": "wazuh-alerts-test", "_id": "unknown", "_source": {"new": "shape"}}
    )
    fallback = normalizer.normalize(unknown, tenant_id, source_id)
    assert fallback.title == "Unclassified security finding"
    assert fallback.severity == 0
    assert fallback.source_occurred_at is None
    assert fallback.effective_time_basis is EffectiveTimeBasis.INGESTED
    assert fallback.normalization.status is NormalizationStatus.PARTIAL
    assert "source_timestamp_missing_or_invalid" in fallback.normalization.issue_codes


def test_canonical_finding_is_immutable_and_fingerprint_is_unicode_stable() -> None:
    tenant_id = uuid4()
    item = finding(tenant_id)
    with pytest.raises(FrozenInstanceError):
        item.title = "changed"  # type: ignore[misc]
    assert canonical_payload_sha256({"name": "Café"}) == canonical_payload_sha256(
        {"name": "Cafe\u0301"}
    )


def test_evidence_locator_rejects_credentials_and_query_tokens() -> None:
    payload_hash = canonical_payload_sha256({"id": "unsafe"})
    with pytest.raises(ValueError, match="locator"):
        ExternalEvidenceReference(
            source_system="test",
            source_instance_id=uuid4(),
            source_object_type="finding",
            source_object_id="unsafe",
            source_timestamp=datetime.now(UTC),
            locator="opensearch://user:secret@index/id?token=secret",
            adapter_version="1",
            normalizer_version="1",
            payload_sha256=payload_hash,
        )


async def test_ingestion_emits_only_for_a_new_revision() -> None:
    tenant_id = uuid4()
    item = finding(tenant_id)
    persisted = PersistedFinding(item.finding_id, uuid4(), 1, True)

    class Repository:
        async def persist(self, value: CanonicalFinding) -> PersistedFinding:
            assert value is item
            return persisted

    class Recorder:
        def __init__(self) -> None:
            self.events: list[DomainEvent] = []

        async def add(self, event: DomainEvent) -> None:
            self.events.append(event)

    recorder = Recorder()
    result = await FindingIngestionService(Repository(), recorder).ingest(
        item, correlation_id=uuid4()
    )
    assert result == persisted
    assert len(recorder.events) == 1
    assert recorder.events[0].event_name == FINDING_NORMALIZED_EVENT
    assert "description" not in recorder.events[0].payload

    class DuplicateRepository:
        async def persist(self, value: CanonicalFinding) -> PersistedFinding:
            return PersistedFinding(value.finding_id, persisted.revision_id, 1, False)

    duplicate_recorder = Recorder()
    await FindingIngestionService(DuplicateRepository(), duplicate_recorder).ingest(
        item, correlation_id=uuid4()
    )
    assert duplicate_recorder.events == []


async def test_invalid_wazuh_cursor_translates_to_canonical_error() -> None:
    client = WazuhIndexerClient(
        WazuhConnectorConfigV1(
            manager_host="wazuh-manager",
            indexer_url="http://opensearch:9200",
            verify_tls=False,
        )
    )
    with pytest.raises(ConnectorError) as captured:
        await client.search_alerts("not-json", None, None, 10)
    assert captured.value.code == ConnectorErrorCode.CURSOR_INVALID


def test_wazuh_configuration_rejects_unsafe_values_without_leaking_secrets() -> None:
    sensitive_value = "sensitive-value-not-for-output"
    with pytest.raises(ValidationError) as captured:
        WazuhConnectorConfigV1(
            manager_host="wazuh-manager/unsafe",
            indexer_url="http://opensearch:9200",
            api_password_secret_ref=sensitive_value,
        )
    assert sensitive_value not in str(captured.value)


def test_domain_has_no_wazuh_imports() -> None:
    domain_root = (
        Path(__file__).parents[2] / "src" / "cyrvanta" / "modules" / "integrations" / "domain"
    )
    for path in domain_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        assert all("wazuh" not in module.lower() for module in imports)


def test_fake_connector_is_not_registered_in_production() -> None:
    assert "fake" not in production_connector_registry().registered_types()
    assert "test-only" not in production_connector_registry().registered_types()
