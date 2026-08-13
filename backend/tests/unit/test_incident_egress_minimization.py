from types import SimpleNamespace
from uuid import uuid4

from cyrvanta.modules.operations.application.reporting import IncidentReportService


def test_external_incident_snapshot_contains_only_authorized_fields() -> None:
    incident = SimpleNamespace(
        id=uuid4(),
        code="INC-001",
        title="Critical incident",
        status="open",
        severity="critical",
        classification="restricted",
        priority="P1",
        version=7,
        detected_at="not-for-egress",
    )
    analysis = SimpleNamespace(
        grounded=True,
        mode="deterministic",
        risk_score=91,
        summary_es="Análisis confirmado",
        summary_en="Confirmed analysis",
        techniques=["not-for-egress"],
        recommendations=["not-for-egress"],
    )

    result = IncidentReportService.minimize_for_egress(incident, analysis)

    assert set(result) == {"incident", "risk", "analysis"}
    assert set(result["incident"]) == {
        "id",
        "code",
        "title",
        "status",
        "severity",
        "classification",
    }
    assert result["risk"] == {"score": 91}
    assert set(result["analysis"]) == {"grounded", "mode", "summary_es", "summary_en"}
