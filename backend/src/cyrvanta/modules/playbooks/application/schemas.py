from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PlaybookExecutionResponse(BaseModel):
    id: UUID
    authorization_id: UUID | None
    source_event_id: UUID | None
    proposal_id: UUID | None
    incident_id: UUID
    playbook_version_id: UUID
    origin: str
    execution_mode: str
    status: str
    inputs: dict[str, object]
    result: dict[str, object] | None
    error_code: str | None
    adapter_execution_id: str | None
    claimed_at: datetime | None
    deadline_at: datetime
    completed_at: datetime | None
    created_at: datetime


class PlaybookExecutionList(BaseModel):
    items: list[PlaybookExecutionResponse]
    total: int


class ExecutionClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dispatch_id: UUID
    adapter_execution_id: str = Field(min_length=1, max_length=200)
    proposal_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExecutionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    adapter_event_id: UUID
    sequence: int = Field(ge=1, le=32767)
    status: Literal["RUNNING", "SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED"]
    result: dict[str, object] | None = None
    error_code: str | None = Field(default=None, min_length=1, max_length=80)
    safe_detail: str | None = Field(default=None, max_length=2000)
    occurred_at: datetime
