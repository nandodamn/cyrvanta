"""What the feedback ledger can honestly be asked.

A metric here is not a number on a dashboard, it is a claim about the SOC's
own detection quality -- and the reason it needs a versioned definition, a
window and a minimum sample is that such a claim is worthless without them.
"Twelve percent false positives" means nothing unless you know over what
period, out of how many cases, and by whose arithmetic.

Two ratios are computed, matching the two halves the feedback taxonomy
already separates: was the detection right, and did the response work. Both
are deliberately plain counts over a window. A ratio that a supervisor cannot
recompute by hand from the same feedback is a ratio they cannot argue with,
and an unarguable number is the kind that quietly steers decisions.

Framework-free: it takes counts and returns counts, so the arithmetic can be
read and tested without a database.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class MetricCode(StrEnum):
    FALSE_POSITIVE_RATE = "detection.false_positive_rate"
    ACTION_EFFECTIVENESS = "response.action_effectiveness"


# Bumped when the arithmetic or the population changes. A snapshot keeps the
# version it was computed under, so an old number is never silently reread
# under new rules.
DEFINITION_VERSION = 1

# Which outcomes count, per metric. Kept as data rather than conditionals so
# the population of each ratio is legible in one place -- the question
# "what exactly is in the denominator?" is the one every disputed metric
# comes down to.
NUMERATOR: dict[MetricCode, frozenset[str]] = {
    MetricCode.FALSE_POSITIVE_RATE: frozenset({"FALSE_POSITIVE"}),
    MetricCode.ACTION_EFFECTIVENESS: frozenset({"ACTION_EFFECTIVE"}),
}

DENOMINATOR: dict[MetricCode, frozenset[str]] = {
    # Assessed detections only. INCONCLUSIVE and NOT_ASSESSED are absences of
    # a judgement, and counting them as correct would flatter the number.
    MetricCode.FALSE_POSITIVE_RATE: frozenset(
        {"TRUE_POSITIVE", "FALSE_POSITIVE", "BENIGN_TRUE_POSITIVE"}
    ),
    MetricCode.ACTION_EFFECTIVENESS: frozenset(
        {"ACTION_EFFECTIVE", "ACTION_INEFFECTIVE", "ACTION_PARTIAL"}
    ),
}


@dataclass(frozen=True, slots=True)
class Ratio:
    numerator: int
    denominator: int
    minimum_sample_size: int

    @property
    def sufficient_sample(self) -> bool:
        return self.denominator >= self.minimum_sample_size

    @property
    def value(self) -> Decimal:
        """Zero on an empty population rather than an error.

        A window with no assessed feedback is an ordinary fact about a quiet
        month, and it is already reported honestly by `sufficient_sample`
        being false -- the value is what must not be read, not what must not
        be computed.
        """
        if self.denominator == 0:
            return Decimal(0)
        return (Decimal(self.numerator) / Decimal(self.denominator)).quantize(Decimal("0.00000001"))


def tally(outcomes: list[str], code: MetricCode, minimum_sample_size: int) -> Ratio:
    denominator = sum(1 for outcome in outcomes if outcome in DENOMINATOR[code])
    numerator = sum(1 for outcome in outcomes if outcome in NUMERATOR[code])
    return Ratio(
        numerator=numerator,
        denominator=denominator,
        minimum_sample_size=minimum_sample_size,
    )
