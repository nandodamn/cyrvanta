from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from ipaddress import IPv4Address, IPv6Address
from types import MappingProxyType
from urllib.parse import urlsplit
from uuid import UUID


class EffectiveTimeBasis(StrEnum):
    SOURCE = "SOURCE"
    DERIVED = "DERIVED"
    INGESTED = "INGESTED"


class NormalizationStatus(StrEnum):
    VALID = "VALID"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"


class FingerprintMode(StrEnum):
    RAW_DOCUMENT = "RAW_DOCUMENT"
    ADAPTER_MATERIAL = "ADAPTER_MATERIAL"


class EntityKind(StrEnum):
    ASSET = "ASSET"
    ACCOUNT = "ACCOUNT"
    IP_ADDRESS = "IP_ADDRESS"
    DOMAIN = "DOMAIN"
    URL = "URL"
    HASH = "HASH"
    PROCESS = "PROCESS"
    FILE = "FILE"


CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")
ALLOWED_EVIDENCE_SCHEMES = frozenset({"cyrvanta", "opensearch", "test"})


def _aware_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def canonical_payload_sha256(payload: Mapping[str, object]) -> str:
    normalized = unicodedata.normalize(
        "NFC",
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ),
    )
    return sha256(normalized.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class NormalizationAssessment:
    status: NormalizationStatus
    completeness_score: int
    issue_codes: tuple[str, ...]
    adapter_name: str
    adapter_version: str
    normalizer_version: str
    fingerprint_version: str = "1"
    canonical_schema_version: int = 1
    fingerprint_mode: FingerprintMode = FingerprintMode.RAW_DOCUMENT

    def __post_init__(self) -> None:
        if not 0 <= self.completeness_score <= 100:
            raise ValueError("completeness_score must be between 0 and 100")
        if self.status is NormalizationStatus.REJECTED:
            raise ValueError("rejected normalization cannot create a canonical finding")
        if len(self.issue_codes) > 32:
            raise ValueError("normalization issue_codes exceeds maximum")
        if any(not code or len(code) > 80 for code in self.issue_codes):
            raise ValueError("normalization issue code is invalid")
        for value, maximum in (
            (self.adapter_name, 80),
            (self.adapter_version, 40),
            (self.normalizer_version, 40),
            (self.fingerprint_version, 20),
        ):
            if not value or len(value) > maximum:
                raise ValueError("normalization version metadata is invalid")


@dataclass(frozen=True, slots=True)
class CanonicalEntityReference:
    kind: EntityKind
    value: str
    namespace: str | None = None
    normalized_value: str | None = None
    display_value: str | None = None
    attributes: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.value or len(self.value) > 512:
            raise ValueError("entity value is empty or too long")
        if len(self.attributes) > 16:
            raise ValueError("entity attributes exceeds maximum")
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))

    @property
    def entity_type(self) -> str:
        return self.kind.value.lower()

    @property
    def display_name(self) -> str | None:
        return self.display_value


@dataclass(frozen=True, slots=True)
class CanonicalProcess:
    name: str | None = None
    pid: int | None = None
    command_line: str | None = None
    executable: str | None = None

    def __post_init__(self) -> None:
        if self.pid is not None and self.pid < 0:
            raise ValueError("pid must be non-negative")


@dataclass(frozen=True, slots=True)
class CanonicalFile:
    path: str | None = None
    name: str | None = None
    sha256: str | None = None

    def __post_init__(self) -> None:
        if self.sha256 is not None and (
            len(self.sha256) != 64
            or any(character not in "0123456789abcdefABCDEF" for character in self.sha256)
        ):
            raise ValueError("sha256 is invalid")


@dataclass(frozen=True, slots=True)
class CanonicalIndicator:
    indicator_type: str
    value: str
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class ExternalEvidenceReference:
    source_system: str
    source_instance_id: UUID
    source_object_type: str
    source_object_id: str
    source_timestamp: datetime | None
    locator: str
    adapter_version: str
    normalizer_version: str
    payload_sha256: str

    def __post_init__(self) -> None:
        if self.source_timestamp is not None:
            object.__setattr__(
                self,
                "source_timestamp",
                _aware_utc(self.source_timestamp, "source_timestamp"),
            )
        if len(self.payload_sha256) != 64:
            raise ValueError("payload_sha256 is invalid")
        if not self.locator or len(self.locator) > 2048:
            raise ValueError("evidence locator is empty or too long")
        parsed = urlsplit(self.locator)
        if (
            parsed.scheme not in ALLOWED_EVIDENCE_SCHEMES
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("evidence locator is not allowed")


@dataclass(frozen=True, slots=True)
class CanonicalFinding:
    finding_id: UUID
    tenant_id: UUID
    integration_id: UUID
    source_system: str
    source_instance_id: UUID
    source_object_type: str
    source_object_id: str
    source_occurred_at: datetime | None
    observed_at: datetime
    effective_at: datetime
    effective_time_basis: EffectiveTimeBasis
    title: str
    severity_score: int
    status: str
    evidence_reference: ExternalEvidenceReference
    payload_fingerprint: str
    normalization: NormalizationAssessment
    description: str | None = None
    confidence: float | None = None
    category: str | None = None
    rule_reference: str | None = None
    entity_references: tuple[CanonicalEntityReference, ...] = ()
    host: CanonicalEntityReference | None = None
    user: CanonicalEntityReference | None = None
    source_ip: IPv4Address | IPv6Address | None = None
    destination_ip: IPv4Address | IPv6Address | None = None
    process: CanonicalProcess | None = None
    file: CanonicalFile | None = None
    indicators: tuple[CanonicalIndicator, ...] = ()
    labels: Mapping[str, str] = field(default_factory=dict)
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", _aware_utc(self.observed_at, "observed_at"))
        object.__setattr__(self, "effective_at", _aware_utc(self.effective_at, "effective_at"))
        if self.source_occurred_at is not None:
            object.__setattr__(
                self,
                "source_occurred_at",
                _aware_utc(self.source_occurred_at, "source_occurred_at"),
            )
        if not 0 <= self.severity_score <= 100:
            raise ValueError("severity_score must be between 0 and 100")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if not self.title or len(self.title) > 500:
            raise ValueError("title is empty or too long")
        if not self.source_object_id or len(self.source_object_id) > 512:
            raise ValueError("source_object_id is empty or too long")
        if (
            CODE_PATTERN.fullmatch(self.source_system) is None
            or len(self.source_system) > 80
            or CODE_PATTERN.fullmatch(self.source_object_type) is None
            or len(self.source_object_type) > 80
        ):
            raise ValueError("source code is invalid")
        if not self.status or len(self.status) > 80:
            raise ValueError("status is empty or too long")
        if self.description is not None and len(self.description) > 4000:
            raise ValueError("description is too long")
        if self.category is not None and len(self.category) > 120:
            raise ValueError("category is too long")
        if self.rule_reference is not None and len(self.rule_reference) > 200:
            raise ValueError("rule_reference is too long")
        if len(self.entity_references) > 32 or len(self.indicators) > 32:
            raise ValueError("canonical reference collection exceeds maximum")
        if len(self.labels) > 32:
            raise ValueError("labels exceeds maximum")
        if len(self.payload_fingerprint) != 64:
            raise ValueError("payload_fingerprint is invalid")
        if self.evidence_reference.payload_sha256 != self.payload_fingerprint:
            raise ValueError("evidence and finding payload fingerprints differ")
        if self.schema_version != self.normalization.canonical_schema_version:
            raise ValueError("canonical schema versions differ")
        object.__setattr__(self, "labels", MappingProxyType(dict(self.labels)))

    @property
    def id(self) -> UUID:
        return self.finding_id

    @property
    def occurred_at(self) -> datetime:
        return self.effective_at

    @property
    def ingested_at(self) -> datetime:
        return self.observed_at

    @property
    def severity(self) -> int:
        return self.severity_score

    @property
    def raw_reference(self) -> ExternalEvidenceReference:
        return self.evidence_reference

    @property
    def normalized_payload_version(self) -> str:
        return str(self.schema_version)

    def all_entity_references(self) -> Sequence[CanonicalEntityReference]:
        values = list(self.entity_references)
        if self.host is not None:
            values.append(self.host)
        if self.user is not None:
            values.append(self.user)
        return tuple(values)
