from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Any


class ActionImpact(StrEnum):
    OBSERVATIONAL = "OBSERVATIONAL"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ResponseMode(StrEnum):
    RECOMMENDATION_ONLY = "RECOMMENDATION_ONLY"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"
    DUAL_APPROVAL = "DUAL_APPROVAL"
    AUTOMATIC = "AUTOMATIC"


class EvaluationOutcome(StrEnum):
    DENIED = "DENIED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    DUAL_APPROVAL_REQUIRED = "DUAL_APPROVAL_REQUIRED"
    ELIGIBLE_FOR_AUTOMATIC = "ELIGIBLE_FOR_AUTOMATIC"


@dataclass(frozen=True)
class PolicyResult:
    outcome: EvaluationOutcome
    required_approvals: int
    reason_codes: tuple[str, ...]


def canonical_fingerprint(value: dict[str, Any]) -> str:
    material = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(material).hexdigest()


def evaluate_policy(
    *,
    impact: ActionImpact,
    requested_mode: ResponseMode,
    global_kill_switch: bool,
    tenant_kill_switch: bool,
    is_simulated: bool,
    automatic_response_enabled: bool = False,
) -> PolicyResult:
    if global_kill_switch or tenant_kill_switch:
        return PolicyResult(EvaluationOutcome.DENIED, 0, ("KILL_SWITCH_ACTIVE",))
    if impact is ActionImpact.CRITICAL:
        return PolicyResult(EvaluationOutcome.DENIED, 0, ("CRITICAL_ACTION_DENIED",))
    if requested_mode is ResponseMode.RECOMMENDATION_ONLY:
        return PolicyResult(EvaluationOutcome.DENIED, 0, ("RECOMMENDATION_ONLY",))
    if requested_mode is ResponseMode.AUTOMATIC:
        if not automatic_response_enabled:
            return PolicyResult(EvaluationOutcome.DENIED, 0, ("AUTOMATIC_DISABLED",))
        return PolicyResult(EvaluationOutcome.ELIGIBLE_FOR_AUTOMATIC, 0, ("AUTOMATIC_APPROVED",))
    if impact is ActionImpact.HIGH or requested_mode is ResponseMode.DUAL_APPROVAL:
        return PolicyResult(
            EvaluationOutcome.DUAL_APPROVAL_REQUIRED,
            2,
            ("DUAL_CONTROL_REQUIRED",),
        )
    reason = "SYNTHETIC_APPROVAL_REQUIRED" if is_simulated else "HUMAN_APPROVAL_REQUIRED"
    return PolicyResult(EvaluationOutcome.APPROVAL_REQUIRED, 1, (reason,))


def validate_target_limit(impact: ActionImpact, target_count: int) -> None:
    limits = {
        ActionImpact.OBSERVATIONAL: 100,
        ActionImpact.LOW: 10,
        ActionImpact.MODERATE: 1,
        ActionImpact.HIGH: 1,
        ActionImpact.CRITICAL: 0,
    }
    if target_count < 1 or target_count > limits[impact]:
        raise ValueError("Target count exceeds the approved impact limit")
