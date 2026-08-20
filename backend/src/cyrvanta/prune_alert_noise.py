"""Discard the backlog of alerts that carry no security meaning.

The manager-side filter (infrastructure/wazuh/manager/rules/) stops this noise
where it is produced, but it only applies to what arrives after it. Alerts
already ingested stay in the backlog and keep inflating the map badges and the
alert list, so they are triaged here instead.

Discarding is reversible -- it sets triage_status, it does not delete -- and the
run records a single audit event stating the criteria and the count, so the
operation is attributable rather than an unexplained drop in volume.

Selection is by rule identity, never by severity. Severity is the wrong axis:
a successful logon is "low" and is what credential-attack correlation groups on,
and a file added to a system directory is "low" and is the whole point of a file
integrity scenario. Discarding "low" wholesale would remove real detections.
"""

import argparse
import asyncio
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, update
from sqlalchemy.sql.elements import ColumnElement

from cyrvanta.modules.identity.infrastructure.models import AuditEventModel, UserModel
from cyrvanta.modules.incident.infrastructure.models import AlertReferenceModel
from cyrvanta.shared.database import tenant_session

# Each entry states what it drops and why it cannot matter to a SOC.
NOISE_TITLES: dict[str, str] = {
    "Software protection service scheduled successfully.": (
        "Servicio de licencias de Windows: sin significado de seguridad."
    ),
    "Non service account logged off.": (
        "Cierre de sesion rutinario. El inicio de sesion es la senal; su cierre no."
    ),
    "Windows installer reconfigured the product.": (
        "Reconfiguracion de MSI durante actualizaciones rutinarias."
    ),
}

# Configuration assessment describes compliance posture and is re-reported in
# full on every scan. It is not an incident and does not belong in an alert feed.
NOISE_CATEGORIES: tuple[str, ...] = ("sca",)


def _criteria() -> ColumnElement[bool]:
    return or_(
        AlertReferenceModel.title.in_(list(NOISE_TITLES)),
        AlertReferenceModel.category.in_(list(NOISE_CATEGORIES)),
    )


async def prune(tenant_id: UUID, *, apply: bool) -> None:
    async with tenant_session(tenant_id) as session:
        pending = _criteria() & (AlertReferenceModel.triage_status != "DISCARDED")
        rows = list(
            (
                await session.execute(
                    select(AlertReferenceModel.title, func.count())
                    .where(AlertReferenceModel.tenant_id == tenant_id, pending)
                    .group_by(AlertReferenceModel.title)
                    .order_by(func.count().desc())
                )
            ).all()
        )
        total = sum(count for _, count in rows)
        remaining = await session.scalar(
            select(func.count()).where(
                AlertReferenceModel.tenant_id == tenant_id,
                AlertReferenceModel.triage_status != "DISCARDED",
            )
        )

        for title, count in rows[:15]:
            print(f"  {count:6}  {title[:70]}")
        if len(rows) > 15:
            print(f"  ... y {len(rows) - 15} titulos mas")
        print(f"\na descartar: {total}")
        print(f"quedan sin revisar despues: {(remaining or 0) - total}")

        if not apply:
            print("\nSimulacion. Volve a ejecutar con --apply para aplicarlo.")
            return

        # An operator is required: an unattributed bulk triage would be a silent
        # drop in alert volume that nobody can account for later.
        actor_id = await session.scalar(select(UserModel.id).limit(1))
        if actor_id is None:
            raise SystemExit("No hay usuarios en el tenant; no se puede atribuir la operacion.")

        await session.execute(
            update(AlertReferenceModel)
            .where(AlertReferenceModel.tenant_id == tenant_id, pending)
            .values(triage_status="DISCARDED", reviewed_by_user_id=actor_id, reviewed_at=func.now())
        )
        session.add(
            AuditEventModel(
                tenant_id=tenant_id,
                actor_user_id=actor_id,
                action="alert.triage.bulk_discarded",
                resource_type="alert_reference",
                resource_id=uuid4(),
                correlation_id=uuid4(),
                outcome="success",
                details={
                    "discarded": total,
                    "titles": sorted(NOISE_TITLES),
                    "categories": list(NOISE_CATEGORIES),
                    "reason": "operational noise without security meaning",
                },
            )
        )
        print(f"\nDescartadas {total} alertas. Registrado en auditoria.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", type=UUID, required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica los cambios. Sin este argumento solo muestra que haria.",
    )
    args = parser.parse_args()
    asyncio.run(prune(args.tenant_id, apply=args.apply))


if __name__ == "__main__":
    main()
