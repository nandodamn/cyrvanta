"""Score how suspicious an entity looks, from alarms that match no rule.

Rule correlation answers "does this match a pattern someone wrote down?". It
is precise and it is blind to everything nobody anticipated. This answers a
different question -- "is activity piling up on this host, user or address?"
-- which needs no pattern at all, only concentration.

Two properties matter more than the arithmetic:

**Repeating one alarm does not make an entity suspicious; different alarms do.**
A host reporting the same logon 3194 times is noisy, not compromised. A host
reporting five different kinds of security event in an hour is worth a look
even when no single one of them is alarming. So a signal type is counted once
on its severity, repetition adds only a little and is capped, and the real
driver is how many *distinct* things are happening.

**What a host already does every day is not evidence.** This was learned the
hard way: scored without it, the lab's Windows agent reached 100/70 purely by
being a working computer -- 22 different routine events (registry writes, VSS
timeouts, installer activity), none alarming, adding up through sheer variety.
Severity does not separate routine from interesting either, since a failed SSH
login is only level 5. What separates them is whether the host has done it
before. A signal already seen on this entity in the baseline period is treated
as background and barely counts; a signal never seen there carries full weight
and is the only kind that earns the diversity bonus.

**Old evidence stops counting.** Contributions decay by half-life, so a score
reflects what is happening now rather than accumulating forever. The same
inputs always produce the same score: nothing is stored and mutated, every
score is recomputed from the observations in the window, so a score can always
be re-derived and explained rather than being taken on trust.

This is deliberately not a probability and not a verdict. It decides what
deserves a human's attention, never what is true.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from math import log2

DEFAULT_HALF_LIFE_HOURS = 2.0
DEFAULT_WINDOW_HOURS = 6
# How far back "normal" is learned from. Long enough that a weekly job counts
# as routine, short enough that a decommissioned habit stops excusing itself.
DEFAULT_BASELINE_DAYS = 7
DEFAULT_THRESHOLD = 70
# Each *new-for-this-entity* signal beyond the first adds this much. It is the
# heaviest term on purpose: severity alone is a weak discriminator here (a
# failed SSH login is level 5), while a host doing several things it has never
# done before is the strongest evidence available without a written rule.
DIVERSITY_POINTS = 10
# Repetition of one signal is worth something -- ten failures are not one
# failure -- but far less than a second kind of signal, and it stops growing.
MAX_REPETITION_POINTS = 2.0
MAX_SCORE = 100
# What a signal is worth once the entity is known to produce it routinely. Not
# zero: a host doing more of its usual thing can still matter, it just is not
# by itself a reason to wake anyone.
ROUTINE_WEIGHT = 0.25


@dataclass(frozen=True, slots=True)
class RiskObservation:
    """One alarm, reduced to what scoring needs."""

    entity_key: str
    signal_key: str
    title: str
    severity_score: int
    effective_at: datetime

    def __post_init__(self) -> None:
        if self.effective_at.tzinfo is None or self.effective_at.utcoffset() is None:
            raise ValueError("effective_at must be timezone-aware")
        object.__setattr__(self, "effective_at", self.effective_at.astimezone(UTC))


@dataclass(frozen=True, slots=True)
class RiskContribution:
    """Why the score is what it is, for one kind of signal."""

    signal_key: str
    title: str
    occurrences: int
    severity_score: int
    points: int
    most_recent: datetime
    # False when the entity has produced this signal before. Shown to the
    # analyst because "this host has never done this" is usually the whole
    # reason the score is worth looking at.
    is_new_for_entity: bool = True


@dataclass(frozen=True, slots=True)
class EntityRisk:
    entity_key: str
    score: int
    threshold: int
    window_start: datetime
    window_end: datetime
    contributions: tuple[RiskContribution, ...]
    fingerprint: str

    @property
    def is_suspicious(self) -> bool:
        return self.score >= self.threshold

    @property
    def distinct_signals(self) -> int:
        return len(self.contributions)

    @property
    def new_signals(self) -> int:
        return sum(1 for item in self.contributions if item.is_new_for_entity)


def _decay(age: timedelta, half_life_hours: float) -> float:
    hours = max(age.total_seconds(), 0.0) / 3600.0
    return float(0.5 ** (hours / half_life_hours))


def score_entity(
    entity_key: str,
    observations: tuple[RiskObservation, ...],
    *,
    now: datetime,
    threshold: int = DEFAULT_THRESHOLD,
    window_hours: int = DEFAULT_WINDOW_HOURS,
    half_life_hours: float = DEFAULT_HALF_LIFE_HOURS,
    baseline: frozenset[tuple[str, str]] = frozenset(),
) -> EntityRisk:
    """`baseline` holds (entity_key, signal_key) pairs seen before the window.

    An empty baseline means nothing is known to be routine yet, so everything
    counts as new. That is the safe direction for a fresh deployment -- it errs
    towards showing an analyst too much rather than staying silent -- but it
    does mean scores settle down only once there is history to compare against.
    """
    reference = now.astimezone(UTC)
    window_start = reference - timedelta(hours=window_hours)
    inside = [
        item
        for item in observations
        if item.entity_key == entity_key and window_start <= item.effective_at <= reference
    ]

    grouped: dict[str, list[RiskObservation]] = {}
    for item in inside:
        grouped.setdefault(item.signal_key, []).append(item)

    contributions: list[RiskContribution] = []
    total = 0.0
    novel = 0
    for signal_key in sorted(grouped):
        items = grouped[signal_key]
        newest = max(item.effective_at for item in items)
        severity = max(item.severity_score for item in items)
        decay = _decay(reference - newest, half_life_hours)
        # Severity carries the weight of the signal itself; repetition adds a
        # capped, sub-linear amount so a thousand copies of one alarm cannot
        # outweigh a second, different alarm.
        repetition = min(log2(len(items)) * 0.5, MAX_REPETITION_POINTS) if len(items) > 1 else 0.0
        is_new = (entity_key, signal_key) not in baseline
        novel += 1 if is_new else 0
        points = (severity / 10.0 + repetition) * decay * (1.0 if is_new else ROUTINE_WEIGHT)
        total += points
        contributions.append(
            RiskContribution(
                signal_key=signal_key,
                title=max(items, key=lambda item: item.effective_at).title,
                occurrences=len(items),
                severity_score=severity,
                points=round(points),
                most_recent=newest,
                is_new_for_entity=is_new,
            )
        )

    # Only new signals earn the diversity bonus. A busy machine is varied by
    # nature; a machine doing several things it has never done is not.
    if novel:
        total += DIVERSITY_POINTS * (novel - 1)
    score = max(0, min(MAX_SCORE, round(total)))

    # Identifies the evidence, not the moment: the same observations always
    # fingerprint the same, so a sweep that finds nothing new can recognise it
    # and stay quiet instead of reopening what it already reported.
    material = {
        "algorithm": 1,
        "entity_key": entity_key,
        "signals": [
            {
                "signal": item.signal_key,
                "occurrences": item.occurrences,
                "most_recent": item.most_recent.isoformat(),
                "new": item.is_new_for_entity,
            }
            for item in contributions
        ],
    }
    fingerprint = sha256(
        json.dumps(material, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()

    return EntityRisk(
        entity_key=entity_key,
        score=score,
        threshold=threshold,
        window_start=window_start,
        window_end=reference,
        contributions=tuple(contributions),
        fingerprint=fingerprint,
    )


def score_all(
    observations: tuple[RiskObservation, ...],
    *,
    now: datetime,
    threshold: int = DEFAULT_THRESHOLD,
    window_hours: int = DEFAULT_WINDOW_HOURS,
    half_life_hours: float = DEFAULT_HALF_LIFE_HOURS,
    baseline: frozenset[tuple[str, str]] = frozenset(),
) -> tuple[EntityRisk, ...]:
    """Every entity present in the observations, most suspicious first."""
    keys = sorted({item.entity_key for item in observations})
    scored = [
        score_entity(
            key,
            observations,
            now=now,
            threshold=threshold,
            window_hours=window_hours,
            half_life_hours=half_life_hours,
            baseline=baseline,
        )
        for key in keys
    ]
    return tuple(sorted(scored, key=lambda item: (-item.score, item.entity_key)))
