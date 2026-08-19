"""The shipped rule definitions must survive the parser the engine uses.

A correlation rule is data, so nothing type-checks it. These tests run the
definitions through `SqlCorrelationRepository._rule()` -- the same code the
worker calls -- so a malformed definition fails here instead of failing
silently in production, where a rejected rule just means detections quietly
stop happening.
"""

from types import SimpleNamespace

import pytest

from cyrvanta.load_correlation_rules import RULES, canonical
from cyrvanta.modules.correlation.infrastructure.repository import SqlCorrelationRepository

# Windows registry syscheck. These fire thousands of times on a single asset,
# so a rule grouping by asset that selected them would open an incident in
# nearly every window.
REGISTRY_RULE_IDS = frozenset({"594", "597", "598", "750", "751", "752"})


def parsed(code: str):
    entry = RULES[code]
    _text, digest = canonical(entry["definition"])
    model = SimpleNamespace(
        rule_code=code,
        version=entry["version"],
        definition=entry["definition"],
        definition_sha256=digest,
    )
    return SqlCorrelationRepository._rule(model)


@pytest.mark.parametrize("code", sorted(RULES))
def test_every_shipped_rule_parses(code: str) -> None:
    rule = parsed(code)
    assert rule.code == code
    assert rule.selectors
    assert 0 <= rule.threshold <= 100


@pytest.mark.parametrize("code", sorted(RULES))
def test_selector_codes_are_unique_per_rule(code: str) -> None:
    """Two selectors sharing a code would collapse into one signal and quietly
    stop the rule from ever reaching distinct_signal_pattern.
    """
    codes = [selector["code"] for selector in RULES[code]["definition"]["selectors"]]
    assert len(codes) == len(set(codes))


@pytest.mark.parametrize("code", sorted(RULES))
def test_multi_signal_rules_offer_more_than_one_signal(code: str) -> None:
    rule = parsed(code)
    if rule.min_severity is not None:
        return
    assert len({selector.code for selector in rule.selectors}) >= 2


def test_canonical_hash_is_stable_and_order_independent() -> None:
    definition = RULES["host-integrity-compromise"]["definition"]
    reordered = dict(reversed(list(definition.items())))
    assert canonical(definition) == canonical(reordered)


def test_host_integrity_rule_excludes_windows_registry_noise() -> None:
    """Encodes the volume decision as a constraint: registry syscheck belongs
    to one very loud asset, and asset grouping would turn it into a flood.
    """
    rule = parsed("host-integrity-compromise")
    assert rule.grouping == "asset"
    assert not {selector.value for selector in rule.selectors} & REGISTRY_RULE_IDS


def test_single_signal_rule_declares_a_minimum_severity() -> None:
    rule = parsed("critical-single-signal")
    assert rule.min_severity == 70
    assert rule.grouping == "asset"


def test_no_rule_groups_by_source_ip_on_signals_that_carry_none() -> None:
    """Wazuh emits no data.srcip for the Windows logon rules (verified over
    3194 events), and syscheck findings have no source IP at all. A rule
    grouping by source_ip on those can never match -- it would look loaded and
    detect nothing.
    """
    without_source_ip = frozenset({"550", "553", "554", "592", "60118", "67028", "60110"})
    for code in RULES:
        rule = parsed(code)
        if rule.grouping != "source_ip":
            continue
        assert not {selector.value for selector in rule.selectors} & without_source_ip
