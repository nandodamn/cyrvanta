from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from cyrvanta.modules.playbooks.application.administration_schemas import (
    ActionList,
    BindingCreate,
    BindingList,
    BindingResponse,
    DefinitionCreate,
    DefinitionList,
    DefinitionResponse,
    DryRunCreate,
    DryRunResponse,
    NativeActionBindingCreate,
    NativeActionBindingResponse,
    ToggleBindingPayload,
    UpdateApprovalGovernancePayload,
    ValidationResponse,
    VersionCreate,
    VersionResponse,
)
from cyrvanta.modules.playbooks.application.administration_service import (
    PlaybookAdministrationConflict,
    PlaybookAdministrationNotFound,
    PlaybookAdministrationService,
)
from cyrvanta.shared.dependencies import SecurityContext, require_permission

router = APIRouter(tags=["playbook-administration"])
PlaybookViewer = Annotated[SecurityContext, Depends(require_permission("playbook.view"))]
PlaybookAuthor = Annotated[SecurityContext, Depends(require_permission("playbook.author"))]
PlaybookReviewer = Annotated[SecurityContext, Depends(require_permission("playbook.review"))]
PlaybookPublisher = Annotated[SecurityContext, Depends(require_permission("playbook.publish"))]
PlaybookExecutor = Annotated[SecurityContext, Depends(require_permission("playbook.execute"))]
BindingManager = Annotated[
    SecurityContext, Depends(require_permission("automation.binding.manage"))
]


def _correlation_id(request: Request) -> UUID:
    return UUID(request.state.correlation_id)


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, PlaybookAdministrationNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.get("/playbook-definitions", response_model=DefinitionList)
async def list_definitions(
    context: PlaybookViewer,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> DefinitionList:
    return await PlaybookAdministrationService().list_definitions(
        context.tenant_id, limit=limit, offset=offset
    )


@router.post(
    "/playbook-definitions",
    response_model=DefinitionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_definition(
    payload: DefinitionCreate, request: Request, context: PlaybookAuthor
) -> DefinitionResponse:
    try:
        return await PlaybookAdministrationService().create_definition(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            payload=payload,
            correlation_id=_correlation_id(request),
        )
    except PlaybookAdministrationConflict as exc:
        raise _translate(exc) from exc


@router.get("/playbook-definitions/{definition_id}", response_model=DefinitionResponse)
async def get_definition(definition_id: UUID, context: PlaybookViewer) -> DefinitionResponse:
    try:
        return await PlaybookAdministrationService().get_definition(
            context.tenant_id, definition_id
        )
    except PlaybookAdministrationNotFound as exc:
        raise _translate(exc) from exc


@router.post(
    "/playbook-definitions/{definition_id}/toggle-binding", response_model=DefinitionResponse
)
async def toggle_definition_binding(
    definition_id: UUID,
    payload: ToggleBindingPayload,
    request: Request,
    context: BindingManager,
) -> DefinitionResponse:
    try:
        return await PlaybookAdministrationService().toggle_definition_binding(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            definition_id=definition_id,
            payload=payload,
            correlation_id=_correlation_id(request),
        )
    except (PlaybookAdministrationConflict, PlaybookAdministrationNotFound) as exc:
        raise _translate(exc) from exc


@router.post(
    "/playbook-definitions/{definition_id}/approval-governance", response_model=DefinitionResponse
)
async def update_approval_governance(
    definition_id: UUID,
    payload: UpdateApprovalGovernancePayload,
    request: Request,
    context: PlaybookReviewer,
) -> DefinitionResponse:
    try:
        return await PlaybookAdministrationService().update_approval_governance(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            definition_id=definition_id,
            payload=payload,
            correlation_id=_correlation_id(request),
        )
    except (PlaybookAdministrationConflict, PlaybookAdministrationNotFound) as exc:
        raise _translate(exc) from exc


@router.post(
    "/playbook-definitions/{definition_id}/versions",
    response_model=VersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    definition_id: UUID,
    payload: VersionCreate,
    request: Request,
    context: PlaybookAuthor,
) -> VersionResponse:
    try:
        return await PlaybookAdministrationService().create_version(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            definition_id=definition_id,
            payload=payload,
            correlation_id=_correlation_id(request),
        )
    except (
        PlaybookAdministrationConflict,
        PlaybookAdministrationNotFound,
        ValueError,
    ) as exc:
        raise _translate(exc) from exc


@router.post("/playbook-versions/{version_id}/validate", response_model=ValidationResponse)
async def validate_version(
    version_id: UUID, request: Request, context: PlaybookReviewer
) -> ValidationResponse:
    try:
        version, errors = await PlaybookAdministrationService().validate_version(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            version_id=version_id,
            correlation_id=_correlation_id(request),
        )
        return ValidationResponse(
            valid=not errors,
            digest=version.artifact_sha256,
            error_codes=errors,
        )
    except PlaybookAdministrationNotFound as exc:
        raise _translate(exc) from exc


@router.get("/playbook-versions/{version_id}/connection-dependencies")
async def get_connection_dependencies(
    version_id: UUID, context: PlaybookReviewer
) -> list[dict[str, object]]:
    try:
        return await PlaybookAdministrationService().validate_connection_dependencies(
            tenant_id=context.tenant_id,
            version_id=version_id,
        )
    except PlaybookAdministrationNotFound as exc:
        raise _translate(exc) from exc
    except PlaybookAdministrationConflict as exc:
        raise _translate(exc) from exc


@router.post("/playbook-versions/{version_id}/publish", response_model=VersionResponse)
async def publish_version(
    version_id: UUID,
    request: Request,
    context: PlaybookPublisher,
    expected_digest: Annotated[str, Header(alias="If-Match", pattern=r"^[0-9a-f]{64}$")],
) -> VersionResponse:
    try:
        return await PlaybookAdministrationService().publish_version(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            version_id=version_id,
            expected_digest=expected_digest,
            correlation_id=_correlation_id(request),
        )
    except (PlaybookAdministrationConflict, PlaybookAdministrationNotFound) as exc:
        raise _translate(exc) from exc


@router.post("/playbook-versions/{version_id}/dry-run", response_model=DryRunResponse)
async def dry_run(
    version_id: UUID,
    payload: DryRunCreate,
    request: Request,
    context: PlaybookExecutor,
) -> DryRunResponse:
    try:
        return await PlaybookAdministrationService().dry_run(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            version_id=version_id,
            inputs=payload.inputs,
            correlation_id=_correlation_id(request),
        )
    except (PlaybookAdministrationConflict, PlaybookAdministrationNotFound) as exc:
        raise _translate(exc) from exc


@router.get("/playbook-actions", response_model=ActionList)
async def list_actions(context: PlaybookViewer) -> ActionList:
    del context
    return PlaybookAdministrationService().list_actions()


@router.get("/playbook-bindings", response_model=BindingList)
async def list_bindings(
    context: PlaybookViewer,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> BindingList:
    return await PlaybookAdministrationService().list_bindings(
        context.tenant_id, limit=limit, offset=offset
    )


@router.post(
    "/playbook-bindings",
    response_model=BindingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_binding(
    payload: BindingCreate, request: Request, context: BindingManager
) -> BindingResponse:
    try:
        return await PlaybookAdministrationService().create_binding(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            payload=payload,
            correlation_id=_correlation_id(request),
        )
    except (PlaybookAdministrationConflict, PlaybookAdministrationNotFound) as exc:
        raise _translate(exc) from exc


@router.post("/playbook-bindings/{binding_id}/probe", response_model=BindingResponse)
async def probe_binding(
    binding_id: UUID, request: Request, context: BindingManager
) -> BindingResponse:
    try:
        return await PlaybookAdministrationService().probe_binding(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            binding_id=binding_id,
            correlation_id=_correlation_id(request),
        )
    except (PlaybookAdministrationConflict, PlaybookAdministrationNotFound) as exc:
        raise _translate(exc) from exc


@router.post(
    "/native-action-bindings",
    response_model=NativeActionBindingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_native_action_binding(
    payload: NativeActionBindingCreate,
    request: Request,
    context: BindingManager,
) -> NativeActionBindingResponse:
    try:
        return await PlaybookAdministrationService().create_action_binding(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            payload=payload,
            correlation_id=_correlation_id(request),
        )
    except PlaybookAdministrationConflict as exc:
        raise _translate(exc) from exc
