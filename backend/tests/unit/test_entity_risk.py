"""The scoring has to survive the noisiest host in the estate.

The lab's Windows agent reports the same logon thousands of times. If volume
drove the score, that host would sit permanently above any threshold and the
whole mechanism would be a nuisance generator. These tests pin the properties
that stop that happening.
"""

from datetime import UTC, datetime, timedelta

import pytest

from cyrvanta.modules.correlation.domain.entity_risk import (
    DEFAULT_THRESHOLD,
    RiskObservation,
    score_all,
    score_entity,
)

NOW = datetime(2026, 8, 19, 18, 0, tzinfo=UTC)
HOST = "ASSET|wazuh-agent|lab-server-01"
OTHER = "ASSET|wazuh-agent|lab-workstation-01"


def observation(
    signal: str,
    *,
    entity: str = HOST,
    severity: int = 49,
    minutes_ago: int = 1,
    title: str = "",
) -> RiskObservation:
    return RiskObservation(
        entity_key=entity,
        signal_key=signal,
        title=title or f"signal {signal}",
        severity_score=severity,
        effective_at=NOW - timedelta(minutes=minutes_ago),
    )


def test_repeating_one_alarm_does_not_make_a_host_suspicious() -> None:
    """This is the Windows agent: 3194 copies of one low logon event."""
    flood = tuple(observation("wazuh:60118", severity=21, minutes_ago=i % 60) for i in range(3194))
    risk = score_entity(HOST, flood, now=NOW)
    assert risk.distinct_signals == 1
    assert risk.is_suspicious is False
    assert risk.score < DEFAULT_THRESHOLD


def test_different_alarms_are_what_raise_the_score() -> None:
    quiet = score_entity(HOST, tuple(observation("wazuh:5760") for _ in range(40)), now=NOW)
    varied = score_entity(
        HOST,
        tuple(observation(f"wazuh:57{index:02d}", severity=70) for index in range(8)),
        now=NOW,
    )
    assert varied.score > quiet.score
    assert varied.is_suspicious is True


def test_one_signal_can_never_outweigh_a_second_kind_of_signal() -> None:
    """The property stated as an inequality: no amount of repetition of a
    single signal beats two distinct signals of the same severity.
    """
    one_repeated = score_entity(
        HOST, tuple(observation("wazuh:5760") for _ in range(5000)), now=NOW
    )
    two_kinds = score_entity(HOST, (observation("wazuh:5760"), observation("wazuh:5715")), now=NOW)
    assert two_kinds.score > one_repeated.score


def test_old_evidence_stops_counting() -> None:
    recent = score_entity(
        HOST,
        (
            observation("a", severity=90, minutes_ago=1),
            observation("b", severity=90, minutes_ago=1),
        ),
        now=NOW,
    )
    stale = score_entity(
        HOST,
        (
            observation("a", severity=90, minutes_ago=300),
            observation("b", severity=90, minutes_ago=300),
        ),
        now=NOW,
    )
    assert stale.score < recent.score


def test_evidence_outside_the_window_is_not_counted_at_all() -> None:
    risk = score_entity(HOST, (observation("a", minutes_ago=60 * 24),), now=NOW, window_hours=6)
    assert risk.contributions == ()
    assert risk.score == 0


def test_entities_do_not_borrow_each_other_s_evidence() -> None:
    observations = (
        observation("a", entity=HOST),
        observation("b", entity=OTHER),
        observation("c", entity=OTHER),
    )
    assert score_entity(HOST, observations, now=NOW).distinct_signals == 1
    assert score_entity(OTHER, observations, now=NOW).distinct_signals == 2


def test_the_score_explains_itself() -> None:
    risk = score_entity(
        HOST,
        (observation("a", severity=70), observation("a", severity=70), observation("b")),
        now=NOW,
    )
    contributions = {item.signal_key: item for item in risk.contributions}
    assert contributions["a"].occurrences == 2
    assert contributions["b"].occurrences == 1
    assert sum(item.points for item in risk.contributions) > 0
    assert all(item.title for item in risk.contributions)


def test_the_same_evidence_always_scores_the_same() -> None:
    observations = (observation("a"), observation("b"), observation("c"))
    first = score_entity(HOST, observations, now=NOW)
    second = score_entity(HOST, tuple(reversed(observations)), now=NOW)
    assert first.score == second.score
    assert first.fingerprint == second.fingerprint


def test_new_evidence_changes_the_fingerprint() -> None:
    base = (observation("a"), observation("b"))
    assert score_entity(HOST, base, now=NOW).fingerprint != (
        score_entity(HOST, (*base, observation("c")), now=NOW).fingerprint
    )


def test_score_is_bounded() -> None:
    overwhelming = tuple(observation(f"signal-{index}", severity=100) for index in range(200))
    assert score_entity(HOST, overwhelming, now=NOW).score == 100


def test_scoring_everything_ranks_the_worst_first() -> None:
    observations = (
        observation("a", entity=HOST),
        observation("a", entity=OTHER),
        observation("b", entity=OTHER),
        observation("c", entity=OTHER, severity=90),
    )
    ranked = score_all(observations, now=NOW)
    assert [item.entity_key for item in ranked] == [OTHER, HOST]


def test_an_entity_with_nothing_scores_zero() -> None:
    risk = score_entity(HOST, (), now=NOW)
    assert risk.score == 0
    assert risk.is_suspicious is False


def test_observations_must_carry_a_timezone() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        RiskObservation(
            entity_key=HOST,
            signal_key="a",
            title="t",
            severity_score=50,
            effective_at=datetime(2026, 8, 19, 18, 0),
        )


def test_what_a_host_already_does_every_day_barely_counts() -> None:
    """The lab's Windows agent, scored honestly. Twenty-two different routine
    events made it reach 100/70 before the baseline existed: variety alone,
    nothing wrong. Once those signals are known to be routine, the same
    activity must fall well below the threshold.
    """
    routine = tuple(observation(f"wazuh:{6000 + index}", severity=35) for index in range(22))
    known = frozenset((HOST, f"wazuh:{6000 + index}") for index in range(22))
    without_baseline = score_entity(HOST, routine, now=NOW)
    with_baseline = score_entity(HOST, routine, now=NOW, baseline=known)
    assert without_baseline.is_suspicious is True
    assert with_baseline.is_suspicious is False


def test_a_host_doing_something_it_has_never_done_still_stands_out() -> None:
    """The other half of the property: the baseline must not silence a real
    intrusion on an otherwise busy machine.
    """
    routine = tuple(observation(f"wazuh:{6000 + index}", severity=35) for index in range(22))
    known = frozenset((HOST, f"wazuh:{6000 + index}") for index in range(22))
    intrusion = routine + tuple(
        observation(signal, severity=70)
        for signal in ("wazuh:5763", "wazuh:5402", "wazuh:554", "wazuh:592")
    )
    risk = score_entity(HOST, intrusion, now=NOW, baseline=known)
    assert risk.new_signals == 4
    assert risk.is_suspicious is True


def test_novelty_is_per_entity_not_global() -> None:
    """A signal being routine somewhere else says nothing about this host."""
    elsewhere = frozenset({(OTHER, "wazuh:5763")})
    risk = score_entity(
        HOST, (observation("wazuh:5763", severity=70),), now=NOW, baseline=elsewhere
    )
    assert risk.contributions[0].is_new_for_entity is True


def test_the_contribution_says_whether_it_was_new() -> None:
    known = frozenset({(HOST, "routine")})
    risk = score_entity(
        HOST, (observation("routine"), observation("first-time")), now=NOW, baseline=known
    )
    flags = {item.signal_key: item.is_new_for_entity for item in risk.contributions}
    assert flags == {"routine": False, "first-time": True}


def test_routine_evidence_is_not_ignored_entirely() -> None:
    known = frozenset({(HOST, "a")})
    assert score_entity(HOST, (observation("a", severity=90),), now=NOW, baseline=known).score > 0
