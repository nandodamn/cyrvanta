from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import MappingProxyType
from uuid import UUID

WINDOW_MINUTES = 10
MAX_WINDOW_MINUTES = 1440
MAX_CANDIDATES = 500
MAX_MEMBERS = 32
MAX_RULES_PER_TRIGGER = 8
ACTIVE_INCIDENT_STATES = frozenset({"new", "triaged", "investigating", "contained", "reopened"})


class CorrelationLimitExceeded(Exception):
    pass


SELECTOR_FIELDS = frozenset({"rule_reference", "category", "severity"})


@dataclass(frozen=True, slots=True)
class SignalSelector:
    """One kind of signal a rule reacts to.

    `field` is usually `rule_reference` or `category`, compared for equality.
    `severity` is different: it matches everything at or above a floor, which
    is the only way to express "anything this source considers serious".

    That matters more than it sounds. With equality alone, covering a source
    means enumerating its rule IDs by hand -- Cyrvanta's four rules name 13 of
    the ~70 IDs this Wazuh actually emits, and level-13 alerts were passing
    unseen simply because nobody had written them down. A list like that also
    rots: every ruleset update adds detections it does not know about. A
    severity floor covers what exists now and what arrives later, without
    anyone remembering to maintain it.
    """

    code: str
    source_system: str
    field: str
    value: str

    def __post_init__(self) -> None:
        if self.field not in SELECTOR_FIELDS:
            raise ValueError("correlation selector field is invalid")
        if self.field == "severity" and not self.value.lstrip("-").isdigit():
            raise ValueError("correlation selector severity must be an integer")

    def matches(self, candidate: CorrelationCandidate) -> bool:
        if candidate.source_system != self.source_system:
            return False
        if self.field == "severity":
            return candidate.severity_score >= int(self.value)
        observed = (
            candidate.rule_reference if self.field == "rule_reference" else candidate.category
        )
        return observed == self.value


GROUPING_KINDS = frozenset({"source_ip", "asset"})


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
    # What "the same thing happening again" means for this rule. Defaults to
    # source_ip, which is what every rule seeded before this field existed
    # already assumes -- adding it changes nothing for them. Host-based
    # detection (file integrity, rootcheck) carries no source IP and can only
    # ever correlate by asset.
    grouping: str = "source_ip"
    # When set, this rule can open an incident from a single finding whose
    # severity reaches this minimum, instead of requiring a pattern of two
    # different signals. Absent means the multi-signal behavior that every
    # rule has had until now.
    min_severity: int | None = None
    # How far back a trigger looks. Rules already carried this field in their
    # stored definition, but the engine ignored it and windowed on a fixed
    # 10-minute UTC bucket instead; it is now the real window length.
    window_minutes: int = WINDOW_MINUTES

    def __post_init__(self) -> None:
        if not self.code or not self.version or len(self.definition_sha256) != 64:
            raise ValueError("correlation rule identity is invalid")
        if not self.selectors or not 0 <= self.threshold <= 100:
            raise ValueError("correlation rule definition is invalid")
        if self.grouping not in GROUPING_KINDS:
            raise ValueError("correlation rule grouping is invalid")
        if self.min_severity is not None and not 0 <= self.min_severity <= 100:
            raise ValueError("correlation rule min_severity is invalid")
        if not 1 <= self.window_minutes <= MAX_WINDOW_MINUTES:
            raise ValueError("correlation rule window_minutes is invalid")


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

    def asset_keys(self) -> tuple[str, ...]:
        # Unlike source_ip, "asset" has no source/destination role to filter
        # on -- it is just the host the finding is about -- so only kind is
        # checked, not a specific namespace.
        return tuple(
            sorted(
                entity.key for entity in self.entities if entity.kind == "ASSET" and entity.value
            )
        )

    def grouping_keys(self, rule: CorrelationRule) -> tuple[str, ...]:
        if rule.grouping == "asset":
            return self.asset_keys()
        return self.source_ip_keys()

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


def window_bounds(value: datetime, minutes: int = WINDOW_MINUTES) -> tuple[datetime, datetime]:
    """The window a trigger looks back over, ending at the trigger itself.

    This replaced fixed UTC buckets, which were blind at their own edges: two
    halves of one attack landing at 12:09 and 12:11 fell in different buckets
    and could never correlate, no matter how obviously related they were. The
    window now travels with the trigger, so what matters is how far apart two
    findings are, not which arbitrary box they happened to land in.

    It looks backward only. A finding cannot be correlated against evidence
    that has not arrived yet; when that later evidence does arrive it becomes
    the trigger and looks back over this one.
    """
    end = value.astimezone(UTC)
    return end - timedelta(minutes=minutes), end


def evaluate_rule(
    rule: CorrelationRule,
    trigger: CorrelationCandidate,
    candidates: tuple[CorrelationCandidate, ...],
) -> CorrelationMatch | None:
    if len(candidates) > rule.max_candidates:
        raise CorrelationLimitExceeded("candidate_limit_exceeded")
    if not trigger.eligible_for(rule) or trigger.selector_code(rule) is None:
        return None
    trigger_keys = trigger.grouping_keys(rule)
    if not trigger_keys:
        return None
    window_start, window_end = window_bounds(trigger.effective_at, rule.window_minutes)
    possible: list[tuple[int, int, str, tuple[CorrelationCandidate, ...]]] = []
    for entity_key in trigger_keys:
        selected = tuple(
            sorted(
                (
                    item
                    for item in candidates
                    if item.eligible_for(rule)
                    and item.is_simulated == trigger.is_simulated
                    and window_start <= item.effective_at <= window_end
                    and entity_key in item.grouping_keys(rule)
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
    # Named after the dimension this rule actually grouped on. Unchanged for
    # every rule seeded before `grouping` existed, since their definitions
    # default to "source_ip" and therefore still produce "exact_source_ip".
    grouping_factor_code = "exact_asset" if rule.grouping == "asset" else "exact_source_ip"
    grouping_factor = FactorResult(
        grouping_factor_code,
        bool(selected),
        40,
        40 if selected else 0,
        revision_ids,
        f"correlation.factor.{grouping_factor_code}",
    )
    diversity_factor = FactorResult(
        "source_diversity",
        distinct_sources >= 2,
        15,
        15 if distinct_sources >= 2 else 0,
        revision_ids,
        "correlation.factor.source_diversity",
    )
    # `required` is carried alongside `factors` instead of being a positional
    # slice of it, so that adding or reordering a factor can never silently
    # change which ones are mandatory.
    factors: tuple[FactorResult, ...]
    required: tuple[FactorResult, ...]
    minimum_severity = rule.min_severity
    if minimum_severity is not None:
        # One alert grave enough stands on its own, so the two factors that
        # demand a *pattern* are not evaluated at all -- waiving them is the
        # entire point of this mode. Severity takes their place as the second
        # mandatory factor. 40 + 45 still sums to the default threshold of 85,
        # and the maximum stays 100, so scores remain comparable across modes.
        # Severity is read from the trigger, not from the group: the claim
        # being made is "this alert is serious by itself".
        severe = trigger.severity_score >= minimum_severity
        factors = (
            grouping_factor,
            FactorResult(
                "critical_severity",
                severe,
                45,
                45 if severe else 0,
                revision_ids,
                "correlation.factor.critical_severity",
            ),
            diversity_factor,
        )
        required = factors[:2]
    else:
        factors = (
            grouping_factor,
            FactorResult(
                "distinct_signal_pattern",
                distinct_selectors >= 2,
                25,
                25 if distinct_selectors >= 2 else 0,
                revision_ids,
                "correlation.factor.distinct_signal_pattern",
            ),
            FactorResult(
                "same_time_window",
                len(selected) >= 2,
                20,
                20 if len(selected) >= 2 else 0,
                revision_ids,
                "correlation.factor.same_time_window",
            ),
            diversity_factor,
        )
        required = factors[:3]
    score = sum(factor.contribution for factor in factors)
    if score < rule.threshold or any(not factor.matched for factor in required):
        return None
    # Deliberately free of any timestamp. With fixed buckets the window start
    # was a stable label shared by every trigger in the same box, so it could
    # sit in this key; a sliding window start moves with every trigger, and
    # keeping it here would give each match its own grouping key and so its own
    # incident -- one attack would arrive as a stream of separate incidents.
    #
    # Dropping it also states the intent better: this identifies "the same rule
    # firing on the same entity", and how long that stays one incident is
    # decided by whether the incident is still open (see `prior_incident`),
    # which is the analyst's decision rather than a clock's.
    grouping_material = "|".join(
        (
            rule.code,
            rule.version,
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
