from datetime import datetime
from enum import StrEnum
from ipaddress import IPv4Address, IPv6Address
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConnectorStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


class ConnectorCapabilities(BaseModel):
    supports_alert_polling: bool = False
    supports_incident_polling: bool = False
    supports_event_search: bool = False
    supports_webhooks: bool = False
    supports_acknowledgement: bool = False
    supports_incident_closure: bool = False
    supports_response_actions: bool = False
    supports_bidirectional_sync: bool = False
    supports_raw_event_retrieval: bool = False
    supports_flow_search: bool = False
    supports_reference_sets: bool = False


class ConnectorHealth(BaseModel):
    status: ConnectorStatus
    latency_ms: int | None = Field(default=None, ge=0)
    error_code: str | None = None
    detail: str | None = None
    checked_at: datetime


class ConnectorConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True)

    integration_id: UUID
    tenant_id: UUID
    connector_type: str
    schema_version: str
    values: dict[str, Any]


class CanonicalEntityReference(BaseModel):
    entity_type: str
    value: str
    display_name: str | None = None


class CanonicalProcess(BaseModel):
    name: str | None = None
    pid: int | None = Field(default=None, ge=0)
    command_line: str | None = None
    executable: str | None = None


class CanonicalFile(BaseModel):
    path: str | None = None
    name: str | None = None
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")


class CanonicalIndicator(BaseModel):
    indicator_type: str
    value: str
    confidence: float | None = Field(default=None, ge=0, le=1)


class ExternalEvidenceReference(BaseModel):
    source_system: str
    source_instance_id: UUID
    source_object_type: str
    source_object_id: str
    source_timestamp: datetime
    locator: str
    adapter_version: str
    normalizer_version: str
    payload_sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")


class CanonicalFinding(BaseModel):
    id: UUID
    tenant_id: UUID
    source_system: str
    source_instance_id: UUID
    source_object_type: str
    source_object_id: str
    occurred_at: datetime
    ingested_at: datetime
    title: str
    description: str | None = None
    severity: int = Field(ge=0, le=100)
    confidence: float | None = Field(default=None, ge=0, le=1)
    category: str | None = None
    status: str
    rule_reference: str | None = None
    host: CanonicalEntityReference | None = None
    user: CanonicalEntityReference | None = None
    source_ip: IPv4Address | IPv6Address | None = None
    destination_ip: IPv4Address | IPv6Address | None = None
    process: CanonicalProcess | None = None
    file: CanonicalFile | None = None
    indicators: list[CanonicalIndicator] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    raw_reference: ExternalEvidenceReference
    normalized_payload_version: str


class CanonicalExternalIncident(BaseModel):
    id: UUID
    tenant_id: UUID
    source_system: str
    source_instance_id: UUID
    source_object_id: str
    occurred_at: datetime
    updated_at: datetime | None = None
    title: str
    description: str | None = None
    severity: int = Field(ge=0, le=100)
    status: str
    finding_references: list[str] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    raw_reference: ExternalEvidenceReference
    normalized_payload_version: str


class FindingBatch(BaseModel):
    items: list[CanonicalFinding]
    next_cursor: str | None = None
    watermark: datetime | None = None


class ExternalIncidentBatch(BaseModel):
    items: list[CanonicalExternalIncident]
    next_cursor: str | None = None
    watermark: datetime | None = None


class CanonicalEventQuery(BaseModel):
    text: str | None = Field(default=None, max_length=500)
    start_time: datetime | None = None
    end_time: datetime | None = None
    limit: int = Field(default=100, ge=1, le=1000)


class EventSearchResult(BaseModel):
    findings: list[CanonicalFinding]
    truncated: bool = False


class CanonicalEvidence(BaseModel):
    reference: ExternalEvidenceReference
    content_type: str
    redacted_payload: dict[str, Any]

