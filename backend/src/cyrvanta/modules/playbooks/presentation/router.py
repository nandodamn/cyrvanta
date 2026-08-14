from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, ValidationError

from cyrvanta.modules.playbooks.application.schemas import (
    ExecutionClaim,
    ExecutionUpdate,
    PlaybookExecutionList,
    PlaybookExecutionResponse,
)
from cyrvanta.modules.playbooks.application.service import (
    PlaybookConflict,
    PlaybookExecutionService,
    PlaybookNotFound,
    PlaybookSecurityError,
)
from cyrvanta.modules.playbooks.domain.models import (
    ExecutionStatus,
    body_sha256,
    canonical_signature_material,
    validate_timestamp,
    verify_signature,
)
from cyrvanta.modules.playbooks.infrastructure.deployment_secrets import (
    resolve_internal_secret,
)
from cyrvanta.shared.config import get_settings
from cyrvanta.shared.dependencies import (
    SecurityContext,
    require_any_permission,
    require_permission,
)

router = APIRouter(tags=["playbook-executions"])
ExecutionReader = Annotated[SecurityContext, Depends(require_permission("playbook.execution.read"))]
ExecutionRunner = Annotated[SecurityContext, Depends(require_permission("response.execute"))]
ExecutionCanceller = Annotated[
    SecurityContext,
    Depends(require_any_permission("playbook.cancel", "response.cancel")),
]


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, PlaybookNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, PlaybookSecurityError):
        return HTTPException(status.HTTP_401_UNAUTHORIZED, "Automation request rejected")
    return HTTPException(status.HTTP_409_CONFLICT, str(exc))


async def _signed_payload[SignedModel: BaseModel](
    request: Request,
    model: type[SignedModel],
    *,
    tenant_id: UUID,
    key_id: str,
    timestamp: int,
    nonce: UUID,
    signature: str,
    secret: str,
    max_body_bytes: int,
) -> tuple[SignedModel, str]:
    settings = get_settings()
    if not secret or key_id != settings.n8n_key_id:
        raise PlaybookSecurityError("Automation signing key is unavailable")
    raw = await request.body()
    if len(raw) > max_body_bytes:
        raise PlaybookSecurityError("Automation payload exceeds the allowed size")
    digest = body_sha256(raw)
    try:
        validate_timestamp(timestamp)
    except ValueError as exc:
        raise PlaybookSecurityError(str(exc)) from exc
    material = canonical_signature_material(
        method=request.method,
        path=request.url.path,
        timestamp=timestamp,
        nonce=str(nonce),
        body_digest=digest,
        tenant_id=str(tenant_id),
    )
    if not verify_signature(secret, material, signature):
        raise PlaybookSecurityError("Automation signature is invalid")
    try:
        return model.model_validate_json(raw), digest
    except ValidationError as exc:
        raise PlaybookSecurityError("Automation payload is invalid") from exc


@router.post(
    "/response-authorizations/{authorization_id}/executions",
    response_model=PlaybookExecutionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def execute_authorization(
    authorization_id: UUID,
    request: Request,
    context: ExecutionRunner,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
) -> PlaybookExecutionResponse:
    try:
        return await PlaybookExecutionService().create_from_authorization(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            authorization_id=authorization_id,
            idempotency_key=idempotency_key,
            correlation_id=UUID(request.state.correlation_id),
        )
    except (PlaybookConflict, PlaybookNotFound) as exc:
        raise _translate(exc) from exc


@router.get("/playbook-executions", response_model=PlaybookExecutionList)
async def list_executions(
    context: ExecutionReader,
    incident_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> PlaybookExecutionList:
    return await PlaybookExecutionService().list(
        context.tenant_id, incident_id=incident_id, limit=limit, offset=offset
    )


@router.get(
    "/playbook-executions/{execution_id}",
    response_model=PlaybookExecutionResponse,
)
async def get_execution(execution_id: UUID, context: ExecutionReader) -> PlaybookExecutionResponse:
    try:
        return await PlaybookExecutionService().get(context.tenant_id, execution_id)
    except PlaybookNotFound as exc:
        raise _translate(exc) from exc


@router.post(
    "/playbook-executions/{execution_id}/rollback",
    response_model=PlaybookExecutionResponse,
)
async def rollback_execution(
    execution_id: UUID,
    request: Request,
    context: ExecutionRunner,
) -> PlaybookExecutionResponse:
    """Revert the containment applied by one succeeded execution.

    Rollback is scoped to an execution, never a standalone playbook: the reverse
    action runs against that execution's own recorded targets.
    """
    try:
        return await PlaybookExecutionService().rollback(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            execution_id=execution_id,
            correlation_id=UUID(request.state.correlation_id),
        )
    except (PlaybookConflict, PlaybookNotFound, ValueError) as exc:
        raise _translate(exc) from exc


@router.post(
    "/playbook-executions/{execution_id}/cancel",
    response_model=PlaybookExecutionResponse,
)
async def cancel_execution(
    execution_id: UUID,
    request: Request,
    context: ExecutionCanceller,
    expected_status: Annotated[str, Header(alias="If-Match", min_length=6, max_length=24)],
) -> PlaybookExecutionResponse:
    try:
        return await PlaybookExecutionService().cancel(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            execution_id=execution_id,
            expected_status=ExecutionStatus(expected_status),
            correlation_id=UUID(request.state.correlation_id),
        )
    except (PlaybookConflict, PlaybookNotFound, ValueError) as exc:
        raise _translate(exc) from exc


@router.post(
    "/internal/playbook-executions/{execution_id}/claim",
    response_model=PlaybookExecutionResponse,
)
async def claim_execution(
    execution_id: UUID,
    request: Request,
    key_id: Annotated[str, Header(alias="X-Cyrvanta-Key-Id", max_length=120)],
    timestamp_value: Annotated[int, Header(alias="X-Cyrvanta-Timestamp")],
    nonce: Annotated[UUID, Header(alias="X-Cyrvanta-Nonce")],
    signature: Annotated[str, Header(alias="X-Cyrvanta-Signature", min_length=64, max_length=64)],
) -> PlaybookExecutionResponse:
    try:
        tenant_id = await PlaybookExecutionService.resolve_tenant(execution_id)
        payload, digest = await _signed_payload(
            request,
            ExecutionClaim,
            tenant_id=tenant_id,
            key_id=key_id,
            timestamp=timestamp_value,
            nonce=nonce,
            signature=signature,
            secret=resolve_internal_secret(
                master_key=get_settings().integration_encryption_key,
                version=get_settings().n8n_internal_key_version,
                purpose="n8n-dispatch",
                explicit_value=get_settings().n8n_dispatch_key,
            ),
            max_body_bytes=65_536,
        )
        return await PlaybookExecutionService().claim(
            tenant_id=tenant_id,
            execution_id=execution_id,
            payload=payload,
            key_id=key_id,
            nonce=nonce,
            body_digest=digest,
            correlation_id=UUID(request.state.correlation_id),
        )
    except (PlaybookConflict, PlaybookNotFound, PlaybookSecurityError) as exc:
        raise _translate(exc) from exc


@router.post(
    "/internal/playbook-executions/{execution_id}/updates",
    response_model=PlaybookExecutionResponse,
)
async def update_execution(
    execution_id: UUID,
    request: Request,
    key_id: Annotated[str, Header(alias="X-Cyrvanta-Key-Id", max_length=120)],
    timestamp_value: Annotated[int, Header(alias="X-Cyrvanta-Timestamp")],
    nonce: Annotated[UUID, Header(alias="X-Cyrvanta-Nonce")],
    signature: Annotated[str, Header(alias="X-Cyrvanta-Signature", min_length=64, max_length=64)],
) -> PlaybookExecutionResponse:
    try:
        tenant_id = await PlaybookExecutionService.resolve_tenant(execution_id)
        payload, digest = await _signed_payload(
            request,
            ExecutionUpdate,
            tenant_id=tenant_id,
            key_id=key_id,
            timestamp=timestamp_value,
            nonce=nonce,
            signature=signature,
            secret=resolve_internal_secret(
                master_key=get_settings().integration_encryption_key,
                version=get_settings().n8n_internal_key_version,
                purpose="n8n-callback",
                explicit_value=get_settings().n8n_callback_key,
            ),
            max_body_bytes=32_768,
        )
        return await PlaybookExecutionService().update(
            tenant_id=tenant_id,
            execution_id=execution_id,
            payload=payload,
            key_id=key_id,
            nonce=nonce,
            body_digest=digest,
            correlation_id=UUID(request.state.correlation_id),
        )
    except (PlaybookConflict, PlaybookNotFound, PlaybookSecurityError, ValueError) as exc:
        raise _translate(exc) from exc
