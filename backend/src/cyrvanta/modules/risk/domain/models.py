import json
from dataclasses import dataclass
from hashlib import sha256

SEVERITY_POINTS = {
    "informational": 5,
    "info": 5,
    "low": 15,
    "medium": 30,
    "high": 45,
    "critical": 60,
}


@dataclass(frozen=True, slots=True)
class RiskInput:
    severity: str
    evidence_count: int
    source_count: int
    supported_mapping_count: int
    normalization_statuses: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RiskFactor:
    code: str
    weight: int
    contribution: int


@dataclass(frozen=True, slots=True)
class RiskResult:
    score: int
    band: str
    factors: tuple[RiskFactor, ...]
    fingerprint: str


def assess_risk(value: RiskInput) -> RiskResult:
    if value.evidence_count < 1 or value.source_count < 1:
        raise ValueError("risk requires at least one authorized evidence item")
    severity = SEVERITY_POINTS.get(value.severity.casefold())
    if severity is None:
        raise ValueError("unknown incident severity")
    corroboration = (
        0
        if value.evidence_count == 1
        else 5
        if value.evidence_count == 2
        else 10
        if value.evidence_count == 3
        else 15
    )
    diversity = 10 if value.source_count >= 2 else 0
    mappings = (
        0 if value.supported_mapping_count == 0 else 5 if value.supported_mapping_count == 1 else 10
    )
    quality = (
        5
        if value.normalization_statuses
        and all(item == "VALID" for item in value.normalization_statuses)
        else 0
    )
    factors = (
        RiskFactor("incident_severity", 60, severity),
        RiskFactor("evidence_corroboration", 15, corroboration),
        RiskFactor("source_diversity", 10, diversity),
        RiskFactor("supported_attack_mappings", 10, mappings),
        RiskFactor("normalization_quality", 5, quality),
    )
    score = sum(item.contribution for item in factors)
    band = (
        "minimal"
        if score <= 19
        else "low"
        if score <= 39
        else "medium"
        if score <= 59
        else "high"
        if score <= 79
        else "critical"
    )
    material = {
        "definition": "incident-risk-v1",
        "input": {
            "severity": value.severity.casefold(),
            "evidence_count": value.evidence_count,
            "source_count": value.source_count,
            "supported_mapping_count": value.supported_mapping_count,
            "normalization_statuses": sorted(value.normalization_statuses),
        },
        "factors": [
            {
                "code": item.code,
                "weight": item.weight,
                "contribution": item.contribution,
            }
            for item in factors
        ],
    }
    fingerprint = sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return RiskResult(score, band, factors, fingerprint)


def deterministic_explanation(
    result: RiskResult, technique_ids: tuple[str, ...]
) -> tuple[str, str]:
    techniques = ", ".join(technique_ids) if technique_ids else "ninguna / none"
    band_es = {
        "minimal": "mínimo",
        "low": "bajo",
        "medium": "medio",
        "high": "alto",
        "critical": "crítico",
    }[result.band]
    contributions = {item.code: item.contribution for item in result.factors}
    es = (
        f"Riesgo {band_es} ({result.score}/100). "
        f"Severidad aporta {contributions['incident_severity']}, corroboración "
        f"{contributions['evidence_corroboration']}, diversidad de fuentes "
        f"{contributions['source_diversity']}, mappings ATT&CK "
        f"{contributions['supported_attack_mappings']} y calidad de normalización "
        f"{contributions['normalization_quality']}. Técnicas sustentadas: {techniques}."
    )
    en = (
        f"{result.band.capitalize()} risk ({result.score}/100). "
        f"Severity contributes {contributions['incident_severity']}, corroboration "
        f"{contributions['evidence_corroboration']}, source diversity "
        f"{contributions['source_diversity']}, supported ATT&CK mappings "
        f"{contributions['supported_attack_mappings']}, and normalization quality "
        f"{contributions['normalization_quality']}. Supported techniques: {techniques}."
    )
    return es[:4000], en[:4000]
