import argparse
import asyncio
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, update

from cyrvanta.modules.threat_knowledge.application.stix import parse_bundle
from cyrvanta.modules.threat_knowledge.infrastructure.models import (
    AttackObjectModel,
    AttackRelationshipModel,
    AttackReleaseModel,
)
from cyrvanta.shared.database import SessionFactory


async def import_attack(path: Path, version: str, source_url: str, activate: bool) -> None:
    parsed = parse_bundle(path)
    async with SessionFactory() as session, session.begin():
        existing = await session.scalar(
            select(AttackReleaseModel).where(
                AttackReleaseModel.domain == "enterprise-attack",
                AttackReleaseModel.version == version,
            )
        )
        if existing is not None:
            if existing.bundle_sha256 != parsed.sha256:
                raise ValueError("release version already exists with a different hash")
            release = existing
        else:
            release = AttackReleaseModel(
                domain="enterprise-attack",
                version=version,
                stix_version="2.1",
                source_url=source_url,
                bundle_sha256=parsed.sha256,
                status="IMPORTED",
            )
            session.add(release)
            await session.flush()
            for attack_object in parsed.objects:
                session.add(
                    AttackObjectModel(
                        release_id=release.id,
                        stix_id=attack_object.stix_id,
                        object_type=attack_object.object_type,
                        external_id=attack_object.external_id,
                        name_en=attack_object.name_en,
                        description_en=attack_object.description_en,
                        is_subtechnique=attack_object.is_subtechnique,
                        revoked=attack_object.revoked,
                        deprecated=attack_object.deprecated,
                        tactic_codes=list(attack_object.tactic_codes),
                        modified=(
                            datetime.fromisoformat(attack_object.modified.replace("Z", "+00:00"))
                            if attack_object.modified
                            else None
                        ),
                    )
                )
            for relationship in parsed.relationships:
                session.add(
                    AttackRelationshipModel(
                        release_id=release.id,
                        stix_id=relationship.stix_id,
                        relationship_type=relationship.relationship_type,
                        source_stix_id=relationship.source_stix_id,
                        target_stix_id=relationship.target_stix_id,
                        revoked=relationship.revoked,
                    )
                )
        if activate:
            await session.execute(
                update(AttackReleaseModel)
                .where(
                    AttackReleaseModel.domain == "enterprise-attack",
                    AttackReleaseModel.status == "ACTIVE",
                    AttackReleaseModel.id != release.id,
                )
                .values(status="RETIRED")
            )
            release.status = "ACTIVE"
            release.activated_at = datetime.now().astimezone()
    print(
        f"ATT&CK {version} imported: {len(parsed.objects)} objects, "
        f"{len(parsed.relationships)} relationships, sha256={parsed.sha256}, "
        f"active={activate}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import an offline ATT&CK STIX 2.1 bundle")
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    asyncio.run(import_attack(args.bundle, args.version, args.source_url, args.activate))


if __name__ == "__main__":
    main()
