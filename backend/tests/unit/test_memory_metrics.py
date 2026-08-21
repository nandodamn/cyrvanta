"""What the feedback ledger can honestly be asked.

A rate without its population is a rumour. These hold the two things that
make the number arguable: exactly which outcomes are counted, and the refusal
to present a ratio drawn from too few cases as if it meant something.
"""

from decimal import Decimal

import pytest

from cyrvanta.modules.governed_memory.domain.metrics import (
    DENOMINATOR,
    NUMERATOR,
    MetricCode,
    tally,
)
from cyrvanta.modules.governed_memory.domain.models import FeedbackOutcome


def test_an_unjudged_case_is_not_counted_as_a_correct_one() -> None:
    """INCONCLUSIVE and NOT_ASSESSED are absences of a judgement. Putting them
    in the denominator of a false-positive rate would flatter the number by
    treating "we never looked" as "we were right".
    """
    outcomes = ["TRUE_POSITIVE", "FALSE_POSITIVE", "INCONCLUSIVE", "NOT_ASSESSED"]
    ratio = tally(outcomes, MetricCode.FALSE_POSITIVE_RATE, minimum_sample_size=1)
    assert ratio.denominator == 2
    assert ratio.numerator == 1
    assert ratio.value == Decimal("0.50000000")


def test_a_benign_detection_was_still_a_real_one() -> None:
    """A true positive nobody needed to act on is not a false positive. It
    counts in the population and not in the numerator, which is the whole
    reason the taxonomy separates the two.
    """
    ratio = tally(
        ["BENIGN_TRUE_POSITIVE", "BENIGN_TRUE_POSITIVE"],
        MetricCode.FALSE_POSITIVE_RATE,
        minimum_sample_size=1,
    )
    assert ratio.denominator == 2
    assert ratio.numerator == 0


def test_detection_and_response_are_measured_separately() -> None:
    """Whether an alarm was right and whether the response worked are
    different questions about different work. Mixing them produces a number
    that improves when either half improves and points at neither.
    """
    outcomes = ["TRUE_POSITIVE", "ACTION_EFFECTIVE", "ACTION_INEFFECTIVE"]
    detection = tally(outcomes, MetricCode.FALSE_POSITIVE_RATE, minimum_sample_size=1)
    response = tally(outcomes, MetricCode.ACTION_EFFECTIVENESS, minimum_sample_size=1)
    assert detection.denominator == 1
    assert response.denominator == 2
    assert response.numerator == 1


def test_too_small_a_sample_is_reported_as_such_rather_than_hidden() -> None:
    """Three cases can produce a confident-looking 33%. The value is still
    computed -- suppressing it would leave a reader guessing -- but it is
    marked as drawn from too little to act on.
    """
    ratio = tally(["TRUE_POSITIVE", "FALSE_POSITIVE"], MetricCode.FALSE_POSITIVE_RATE, 20)
    assert not ratio.sufficient_sample
    assert ratio.value == Decimal("0.50000000")


def test_a_quiet_window_is_a_fact_and_not_an_error() -> None:
    """No assessed feedback in thirty days is an ordinary month, not a failure
    to compute. It reports zero and says the sample is insufficient.
    """
    ratio = tally([], MetricCode.FALSE_POSITIVE_RATE, minimum_sample_size=20)
    assert ratio.value == Decimal(0)
    assert not ratio.sufficient_sample


@pytest.mark.parametrize("code", list(MetricCode))
def test_every_counted_outcome_is_one_the_taxonomy_defines(code: MetricCode) -> None:
    """A metric counting a string the feedback form can never produce would
    read as a permanent zero that nobody could explain.
    """
    known = {outcome.value for outcome in FeedbackOutcome}
    assert NUMERATOR[code] <= known
    assert DENOMINATOR[code] <= known


@pytest.mark.parametrize("code", list(MetricCode))
def test_the_numerator_is_drawn_from_the_population_it_divides(code: MetricCode) -> None:
    """Otherwise a rate could exceed one, which is not a rate."""
    assert NUMERATOR[code] <= DENOMINATOR[code]
