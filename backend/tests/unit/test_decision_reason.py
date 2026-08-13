import pytest

from cyrvanta.modules.decision.application.service import DecisionConflict, DecisionService


def test_decision_reason_is_human_content_and_normalized() -> None:
    assert DecisionService._validated_decision_reason("  reviewed scope  ") == "reviewed scope"

    with pytest.raises(DecisionConflict, match="reason is required"):
        DecisionService._validated_decision_reason("   ")
