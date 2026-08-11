from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from pytest import MonkeyPatch

from cyrvanta.modules.operations.application import service as operations_module
from cyrvanta.modules.operations.application.service import OperationsService
from cyrvanta.modules.threat_knowledge.application.service import EnrichmentUnavailable


def _install_incident_and_session(monkeypatch: MonkeyPatch, incident_id) -> None:
    async def get_incident(_self, _tenant_id, requested_incident_id):
        assert requested_incident_id == incident_id
        return SimpleNamespace(
            id=incident_id,
            detected_at=datetime(2026, 8, 11, tzinfo=UTC),
            title="Unclassified observation",
            description="No evidence has been correlated yet.",
            severity="high",
            classification="unknown",
            status="open",
            is_simulated=False,
        )

    @asynccontextmanager
    async def session_scope(_tenant_id):
        yield object()

    class EventStore:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        @staticmethod
        def recorder(_session):
            return object()

    monkeypatch.setattr(operations_module.IncidentService, "get_incident", get_incident)
    monkeypatch.setattr(operations_module, "tenant_session", session_scope)
    monkeypatch.setattr(operations_module, "SqlEventStore", EventStore)


async def test_analysis_without_persisted_evidence_fails_closed(
    monkeypatch: MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    incident_id = uuid4()
    _install_incident_and_session(monkeypatch, incident_id)

    class MissingEnrichment:
        def __init__(self, *_args) -> None:
            pass

        async def get(self, _tenant_id, _incident_id):
            raise EnrichmentUnavailable("no persisted assessment")

    monkeypatch.setattr(operations_module, "ThreatEnrichmentService", MissingEnrichment)

    result = await OperationsService().analyze(
        tenant_id,
        incident_id,
        record_claims=True,
    )

    assert result.grounded is False
    assert result.mode == "evidence-unavailable"
    assert result.provider == "none"
    assert result.confidence == 0
    assert result.risk_score == 0
    assert result.techniques == []
    assert result.recommendations == []
    assert "Evidencia insuficiente" in result.summary_es
    assert "Insufficient evidence" in result.summary_en


async def test_analysis_projects_only_persisted_supported_enrichment(
    monkeypatch: MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    incident_id = uuid4()
    _install_incident_and_session(monkeypatch, incident_id)

    enrichment = SimpleNamespace(
        risk=SimpleNamespace(score=73),
        explanations=[
            SimpleNamespace(
                locale="es",
                mode="DETERMINISTIC",
                text="Riesgo calculado desde evidencia persistida.",
                provider="template-v1",
                grounded=True,
            ),
            SimpleNamespace(
                locale="en",
                mode="DETERMINISTIC",
                text="Risk calculated from persisted evidence.",
                provider="template-v1",
                grounded=True,
            ),
        ],
        mappings=[
            SimpleNamespace(
                external_id="T1110",
                name_en="Brute Force",
                tactic_codes=["credential-access"],
                status="SUPPORTED",
            ),
            SimpleNamespace(
                external_id="T9999",
                name_en="Rejected mapping",
                tactic_codes=[],
                status="REJECTED",
            ),
        ],
    )

    class PersistedEnrichment:
        def __init__(self, *_args) -> None:
            pass

        async def get(self, _tenant_id, _incident_id):
            return enrichment

    monkeypatch.setattr(operations_module, "ThreatEnrichmentService", PersistedEnrichment)

    result = await OperationsService().analyze(tenant_id, incident_id)

    assert result.grounded is True
    assert result.mode == "deterministic"
    assert result.provider == "template-v1"
    assert result.model == "not-applicable"
    assert result.confidence == 0
    assert result.risk_score == 73
    assert [item.external_id for item in result.techniques] == ["T1110"]
    assert result.recommendations == []
