from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

MAX_BUNDLE_BYTES = 250 * 1024 * 1024
MAX_OBJECTS = 100_000
MAX_RELATIONSHIPS = 500_000
ALLOWED_TYPES = {
    "x-mitre-tactic",
    "attack-pattern",
    "course-of-action",
    "relationship",
    "marking-definition",
}


@dataclass(frozen=True, slots=True)
class ParsedAttackObject:
    stix_id: str
    object_type: str
    external_id: str | None
    name_en: str | None
    description_en: str | None
    is_subtechnique: bool
    revoked: bool
    deprecated: bool
    tactic_codes: tuple[str, ...]
    modified: str | None


@dataclass(frozen=True, slots=True)
class ParsedRelationship:
    stix_id: str
    relationship_type: str
    source_stix_id: str
    target_stix_id: str
    revoked: bool


@dataclass(frozen=True, slots=True)
class ParsedBundle:
    sha256: str
    objects: tuple[ParsedAttackObject, ...]
    relationships: tuple[ParsedRelationship, ...]


def parse_bundle(path: Path) -> ParsedBundle:
    if path.stat().st_size > MAX_BUNDLE_BYTES:
        raise ValueError("ATT&CK bundle exceeds 250 MiB")
    raw = path.read_bytes()
    digest = sha256(raw).hexdigest()
    payload = json.loads(raw)
    if payload.get("type") != "bundle" or not isinstance(payload.get("objects"), list):
        raise ValueError("expected a STIX 2.1 bundle")
    source = payload["objects"]
    if len(source) > MAX_OBJECTS + MAX_RELATIONSHIPS:
        raise ValueError("ATT&CK bundle object limit exceeded")
    objects: list[ParsedAttackObject] = []
    relationships: list[ParsedRelationship] = []
    for item in source:
        if not isinstance(item, dict) or item.get("type") not in ALLOWED_TYPES:
            continue
        kind = str(item["type"])
        if kind == "relationship":
            if len(relationships) >= MAX_RELATIONSHIPS:
                raise ValueError("ATT&CK relationship limit exceeded")
            relationships.append(
                ParsedRelationship(
                    stix_id=str(item["id"]),
                    relationship_type=str(item.get("relationship_type", "")),
                    source_stix_id=str(item["source_ref"]),
                    target_stix_id=str(item["target_ref"]),
                    revoked=bool(item.get("revoked", False)),
                )
            )
            continue
        if len(objects) >= MAX_OBJECTS:
            raise ValueError("ATT&CK object limit exceeded")
        external_id = next(
            (
                str(ref["external_id"])
                for ref in item.get("external_references", [])
                if isinstance(ref, dict)
                and ref.get("source_name") == "mitre-attack"
                and ref.get("external_id")
            ),
            None,
        )
        tactic_codes = tuple(
            sorted(
                {
                    str(phase["phase_name"])
                    for phase in item.get("kill_chain_phases", [])
                    if isinstance(phase, dict)
                    and phase.get("kill_chain_name") == "mitre-attack"
                    and phase.get("phase_name")
                }
            )
        )
        objects.append(
            ParsedAttackObject(
                stix_id=str(item["id"]),
                object_type=kind,
                external_id=external_id,
                name_en=str(item["name"]) if item.get("name") else None,
                description_en=(str(item["description"]) if item.get("description") else None),
                is_subtechnique=bool(item.get("x_mitre_is_subtechnique", False)),
                revoked=bool(item.get("revoked", False)),
                deprecated=bool(item.get("x_mitre_deprecated", False)),
                tactic_codes=tactic_codes,
                modified=str(item["modified"]) if item.get("modified") else None,
            )
        )
    return ParsedBundle(digest, tuple(objects), tuple(relationships))
