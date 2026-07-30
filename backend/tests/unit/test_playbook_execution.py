from datetime import UTC, datetime, timedelta

import pytest

from cyrvanta.modules.playbooks.domain.models import (
    ExecutionStatus,
    body_sha256,
    canonical_signature_material,
    sign_request,
    validate_timestamp,
    validate_transition,
    verify_signature,
)


def test_hmac_signature_binds_method_path_body_nonce_and_tenant() -> None:
    body = b'{"execution_id":"example"}'
    material = canonical_signature_material(
        method="POST",
        path="/api/v1/internal/playbook-executions/example/claim",
        timestamp=1_800_000_000,
        nonce="a8f51816-c5a3-46bf-8d10-13be177aed89",
        body_digest=body_sha256(body),
        tenant_id="fc5e780c-c3a4-4800-b284-f9bc2a626857",
    )
    signature = sign_request("test-secret", material)
    assert verify_signature("test-secret", material, signature)
    assert not verify_signature("other-secret", material, signature)


def test_signature_timestamp_fails_closed_outside_window() -> None:
    now = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)
    validate_timestamp(int((now - timedelta(seconds=120)).timestamp()), now=now)
    with pytest.raises(ValueError, match="outside"):
        validate_timestamp(int((now - timedelta(seconds=121)).timestamp()), now=now)


def test_execution_state_machine_separates_dispatch_from_success() -> None:
    validate_transition(ExecutionStatus.QUEUED, ExecutionStatus.DISPATCHING)
    validate_transition(ExecutionStatus.DISPATCHING, ExecutionStatus.DISPATCHED)
    validate_transition(ExecutionStatus.DISPATCHED, ExecutionStatus.RUNNING)
    validate_transition(ExecutionStatus.RUNNING, ExecutionStatus.SUCCEEDED)
    with pytest.raises(ValueError, match="Invalid"):
        validate_transition(ExecutionStatus.DISPATCHING, ExecutionStatus.SUCCEEDED)
