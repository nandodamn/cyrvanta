from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class IntegrationHealth(BaseModel):
    code: str
    mode: Literal["disabled", "simulated", "live"]
    healthy: bool
    detail: str


class Technique(BaseModel):
    external_id: str
    name_es: str
    name_en: str
    tactic: str


class AnalysisResponse(BaseModel):
    incident_id: UUID
    provider: str
    model: str
    mode: str
    summary_es: str
    summary_en: str
    confidence: float = Field(ge=0, le=1)
    risk_score: int = Field(ge=0, le=100)
    techniques: list[Technique]
    recommendations: list[str]
    grounded: bool


class AutomationRequest(BaseModel):
    incident_id: UUID
    workflow_id: str = Field(min_length=1, max_length=120)
    approved: bool
    idempotency_key: str = Field(min_length=8, max_length=200)


class AutomationResponse(BaseModel):
    execution_id: str
    status: str
    mode: str
    workflow_id: str


class PlaybookConnector(BaseModel):
    node_type: str
    name: str
    credential_names: list[str]


class PlaybookSummary(BaseModel):
    workflow_id: str
    name: str
    active: bool | None
    registered: bool
    version_id: str | None
    connectors: list[PlaybookConnector]


class PlaybookCatalogResponse(BaseModel):
    items: list[PlaybookSummary]
    total: int
    synchronized: bool
    sync_detail: str
    mode: Literal["disabled", "simulated", "live"]


class PlaybookManagementResponse(BaseModel):
    editor_url: str
    local_only: bool
    api_sync_configured: bool
