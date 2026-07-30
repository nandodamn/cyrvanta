from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class ExecutionStatus(StrEnum):
    QUEUED = "QUEUED"
    DISPATCHING = "DISPATCHING"
    DISPATCHED = "DISPATCHED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


TERMINAL_STATUSES = frozenset(
    {
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED,
        ExecutionStatus.TIMED_OUT,
        ExecutionStatus.CANCELLED,
    }
)

ALLOWED_TRANSITIONS = {
    ExecutionStatus.QUEUED: {
        ExecutionStatus.DISPATCHING,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.TIMED_OUT,
    },
    ExecutionStatus.DISPATCHING: {
        ExecutionStatus.DISPATCHED,
        ExecutionStatus.FAILED,
        ExecutionStatus.UNKNOWN,
        ExecutionStatus.TIMED_OUT,
    },
    ExecutionStatus.DISPATCHED: {
        ExecutionStatus.RUNNING,
        ExecutionStatus.FAILED,
        ExecutionStatus.TIMED_OUT,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.UNKNOWN,
    },
    ExecutionStatus.RUNNING: {
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED,
        ExecutionStatus.TIMED_OUT,
        ExecutionStatus.UNKNOWN,
    },
    ExecutionStatus.UNKNOWN: {
        ExecutionStatus.RUNNING,
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED,
        ExecutionStatus.TIMED_OUT,
    },
}


def validate_transition(current: ExecutionStatus, target: ExecutionStatus) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid execution transition: {current} -> {target}")


def body_sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def canonical_signature_material(
    *,
    method: str,
    path: str,
    timestamp: int,
    nonce: str,
    body_digest: str,
    tenant_id: str,
) -> bytes:
    return (
        f"v1\n{method.upper()}\n{path}\n{timestamp}\n{nonce}\n{body_digest}\n{tenant_id}"
    ).encode()


def sign_request(secret: str, material: bytes) -> str:
    return hmac.new(secret.encode(), material, hashlib.sha256).hexdigest()


def verify_signature(secret: str, material: bytes, supplied: str) -> bool:
    expected = sign_request(secret, material)
    return hmac.compare_digest(expected, supplied.lower())


def validate_timestamp(timestamp: int, *, now: datetime | None = None) -> None:
    current = int((now or datetime.now(UTC)).timestamp())
    if abs(current - timestamp) > 120:
        raise ValueError("Signed request timestamp is outside the allowed window")


@dataclass(frozen=True, slots=True)
class WorkflowArtifact:
    code: str
    version: str
    sha256: str
    classification: str

    def __post_init__(self) -> None:
        if len(self.sha256) != 64 or any(char not in "0123456789abcdef" for char in self.sha256):
            raise ValueError("Workflow artifact digest must be lowercase SHA-256")
        if self.classification not in {"demo", "synthetic", "live"}:
            raise ValueError("Workflow classification is invalid")
