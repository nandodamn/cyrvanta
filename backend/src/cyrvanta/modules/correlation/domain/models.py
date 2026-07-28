from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import MappingProxyType
from uuid import UUID

BUCKET_MINUTES = 10
MAX_CANDIDATES = 500
MAX_MEMBERS = 32
MAX_RULES_PER_TRIGGER = 8
ACTIVE_INCIDENT_STATES = frozenset({"new", "triaged", "investigating", "contained", "reopened"})


class CorrelationLimitExceeded(Exception):
    pass


@dataclass(frozen=True, slots=True)
class SignalSelector:
    code: str
    source_system: str
    field: str
    value: str

    def matches(self, candidate: CorrelationCandidate) -> bool:
        if candidate.source_system != self.source_system:
            return False
        observed = (
            candidate.rule_reference if self.field == "rule_reference" else candidate.category
        )
        return observed == self.value


@dataclass(frozen=True, slots=True)
class CorrelationRule:
    code: str
    version: str
    definition_sha256: str
    selectors: tuple[SignalSelector, ...]
    partial_issue_allowlist: frozenset[str]
    threshold: int = 85
    max_candidates: int = MAX_CANDIDATES
    max_members: int = MAX_MEMBERS

    def __post_init__(self) -> None:
        if not self.code or not self.version or len(self.definition_sha256) != 64:
            raise ValueError("correlation rule identity is invalid")
        if not self.selectors or not 0 <= self.threshold <= 100:
            raise ValueError("correlation rule definition is invalid")


@dataclass(frozen=True, slots=True)
class EntityReference:
    kind: str
    value: str
    namespace: str | None

    @property
    def key(self) -> str:
        return f"{self.kind}|{self.namespace or ''}|{self.value}"


@dataclass(frozen=True, slots=True)
class CorrelationCandidate:
    finding_id: UUID
    revision_id: UUID
    integration_id: UUID
    source_system: str
    effective_at: datetime
    effective_time_basis: str
    severity_score: int
    category: str | None
    rule_reference: str | None
    normalization_status: str
    issue_codes: tuple[str, ...]
    entities: tuple[EntityReference, ...]
    is_simulated: bool

    def __post_init__(self) -> None:
        if self.effective_at.tzinfo is None or self.effective_at.utcoffset() is None:
            raise ValueError("effective_at must be timezone-aware")
        object.__setattr__(self, "effective_at", self.effective_at.astimezone(UTC))

    def source_ip_keys(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                entity.key
                for entity in self.entities
                if entity.kind == "IP_ADDRESS" and entity.namespace == "source" and entity.value
            )
        )

    def selector_code(self, rule: CorrelationRule) -> str | None:
        return next(
            (selector.code for selector in rule.selectors if selector.matches(self)),
            None,
        )

    def eligible_for(self, rule: CorrelationRule) -> bool:
        if self.effective_time_basis == "INGESTED":
            return False
        if self.normalization_status == "VALID":
            return True
        return self.normalization_status == "PARTIAL" and set(self.issue_codes).issubset(
            rule.partial_issue_allowlist
        )


@dataclass(frozen=True, slots=True)
class FactorResult:
    code: str
    matched: bool
    weight: int
    contribution: int
    evidence_revision_ids: tuple[UUID, ...]
    explanation_code: str


@dataclass(frozen=True, slots=True)
class CorrelationMatch:
    rule_code: str
    rule_version: str
    rule_definition_sha256: str
    grouping_key_hash: str
    input_fingerprint: str
    window_start: datetime
    window_end: datetime
    score: int
    threshold: int
    entity_key: str
    members: tuple[CorrelationCandidate, ...]
    selector_codes: Mapping[UUID, str]
    factors: tuple[FactorResult, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "selector_codes", MappingProxyType(dict(self.selector_codes)))

    @property
    def is_simulated(self) -> bool:
        return any(member.is_simulated for member in self.members)


def bucket_bounds(value: datetime) -> tuple[datetime, datetime]:
    utc = value.astimezone(UTC)
    minute = (utc.minute // BUCKET_MINUTES) * BUCKET_MINUTES
    start = utc.replace(minute=minute, second=0, microsecond=0)
    return start, start + timedelta(minutes=BUCKET_MINUTES)


def evaluate_rule(
    rule: CorrelationRule,
    trigger: CorrelationCandidate,
    candidates: tuple[CorrelationCandidate, ...],
) -> CorrelationMatch | None:
    if len(candidates) > rule.max_candidates:
        raise CorrelationLimitExceeded("candidate_limit_exceeded")
    if not trigger.eligible_for(rule) or trigger.selector_code(rule) is None:
        return None
    trigger_keys = trigger.source_ip_keys()
    if not trigger_keys:
        return None
    window_start, window_end = bucket_bounds(trigger.effective_at)
    possible: list[tuple[int, int, str, tuple[CorrelationCandidate, ...]]] = []
    for entity_key in trigger_keys:
        selected = tuple(
            sorted(
                (
                    item
                    for item in candidates
                    if item.eligible_for(rule)
                    and item.is_simulated == trigger.is_simulated
                    and window_start <= item.effective_at < window_end
                    and entity_key in item.source_ip_keys()
                    and item.selector_code(rule) is not None
                ),
                key=lambda item: (
                    item.effective_at,
                    str(item.finding_id),
                    str(item.revision_id),
                ),
            )
        )
        selector_count = len(
            {item.selector_code(rule) for item in selected if item.selector_code(rule)}
        )
        possible.append((selector_count, len(selected), entity_key, selected))
    _selector_count, _member_count, entity_key, selected = max(
        possible, key=lambda item: (item[0], item[1], item[2])
    )
    if len(selected) > rule.max_members:
        raise CorrelationLimitExceeded("member_limit_exceeded")
    selector_codes = {
        item.revision_id: code
        for item in selected
        if (code := item.selector_code(rule)) is not None
    }
    revision_ids = tuple(item.revision_id for item in selected)
    distinct_selectors = len(set(selector_codes.values()))
    distinct_sources = len({item.source_system for item in selected})
    factors = (
        FactorResult(
            "exact_source_ip",
            bool(selected),
            40,
            40 if selected else 0,
            revision_ids,
            "correlation.factor.exact_source_ip",
        ),
        FactorResult(
            "distinct_signal_pattern",
            distinct_selectors >= 2,
            25,
            25 if distinct_selectors >= 2 else 0,
            revision_ids,
            "correlation.factor.distinct_signal_pattern",
        ),
        FactorResult(
            "same_time_bucket",
            len(selected) >= 2,
            20,
            20 if len(selected) >= 2 else 0,
            revision_ids,
            "correlation.factor.same_time_bucket",
        ),
        FactorResult(
            "source_diversity",
            distinct_sources >= 2,
            15,
            15 if distinct_sources >= 2 else 0,
            revision_ids,
            "correlation.factor.source_diversity",
        ),
    )
    score = sum(factor.contribution for factor in factors)
    if score < rule.threshold or any(not factor.matched for factor in factors[:3]):
        return None
    grouping_material = "|".join(
        (
            rule.code,
            rule.version,
            window_start.isoformat(),
            entity_key,
            "simulated" if trigger.is_simulated else "real",
        )
    )
    grouping_key_hash = sha256(grouping_material.encode("utf-8")).hexdigest()
    fingerprint_material = {
        "algorithm": 1,
        "definition_sha256": rule.definition_sha256,
        "effective_times": [item.effective_at.isoformat() for item in selected],
        "grouping_key_hash": grouping_key_hash,
        "revision_ids": [str(item.revision_id) for item in selected],
        "rule_code": rule.code,
        "rule_version": rule.version,
    }
    input_fingerprint = sha256(
        json.dumps(
            fingerprint_material,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return CorrelationMatch(
        rule_code=rule.code,
        rule_version=rule.version,
        rule_definition_sha256=rule.definition_sha256,
        grouping_key_hash=grouping_key_hash,
        input_fingerprint=input_fingerprint,
        window_start=window_start,
        window_end=window_end,
        score=score,
        threshold=rule.threshold,
        entity_key=entity_key,
        members=selected,
        selector_codes=selector_codes,
        factors=factors,
    )
