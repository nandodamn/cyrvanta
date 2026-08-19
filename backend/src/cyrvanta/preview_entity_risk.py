"""Show what the entity-risk sweep would say, without it doing anything.

The right threshold is a property of how noisy an estate is, not something
that can be picked in the abstract. This prints the real scores so the number
is chosen against real data, and shows which signals produced each one so a
surprising score can be argued with rather than accepted.

Read-only: it opens no incidents and writes nothing.

    python -m cyrvanta.preview_entity_risk --tenant-id <uuid>
    python -m cyrvanta.preview_entity_risk --tenant-id <uuid> --window-hours 24 --threshold 60
"""

import argparse
import asyncio
from uuid import UUID

from cyrvanta.modules.correlation.application.entity_risk_service import EntityRiskService
from cyrvanta.modules.correlation.domain.entity_risk import (
    DEFAULT_BASELINE_DAYS,
    DEFAULT_HALF_LIFE_HOURS,
    DEFAULT_THRESHOLD,
    DEFAULT_WINDOW_HOURS,
)
from cyrvanta.shared.database import tenant_session


async def preview(
    tenant_id: UUID,
    *,
    threshold: int,
    window_hours: int,
    half_life_hours: float,
    baseline_days: int,
    detail: int,
) -> None:
    async with tenant_session(tenant_id) as session:
        scored, alerts = await EntityRiskService(session).evaluate(
            tenant_id,
            threshold=threshold,
            window_hours=window_hours,
            half_life_hours=half_life_hours,
            baseline_days=baseline_days,
        )

    print(
        f"Ventana: {window_hours}h   Umbral: {threshold}   "
        f"Semivida: {half_life_hours}h   Linea base: {baseline_days}d"
    )
    print(f"Entidades  : {len(scored)}")
    suspicious = [item for item in scored if item.is_suspicious]
    print(f"Sospechosas: {len(suspicious)}  <- abriria un incidente por cada una\n")

    if not scored:
        print("Sin actividad en la ventana. Nada que puntuar.")
        return

    print(f"{'PUNTAJE':>7}  {'SENALES':>7}  {'NUEVAS':>6}  {'ALERTAS':>7}  ENTIDAD")
    for risk in scored:
        mark = "!!" if risk.is_suspicious else "  "
        print(
            f"{mark}{risk.score:>5}  {risk.distinct_signals:>7}  {risk.new_signals:>6}  "
            f"{len(alerts.get(risk.entity_key, ())):>7}  {risk.entity_key}"
        )

    for risk in scored[:detail]:
        print(f"\n--- {risk.entity_key}  ({risk.score}/{risk.threshold})")
        for item in risk.contributions:
            flag = "NUEVA" if item.is_new_for_entity else "rutina"
            print(
                f"    {item.points:>3} pts  x{item.occurrences:<5} sev={item.severity_score:<4}"
                f"{flag:<7}{item.signal_key:<18} {item.title[:46]}"
            )

    if suspicious:
        print(
            "\nSi este resultado te parece correcto, activa el barrido con "
            "ENTITY_RISK_ENABLED=true. Si hay falsos positivos, sube el umbral "
            "o descarta el ruido antes de activarlo."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", type=UUID, required=True)
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    parser.add_argument("--window-hours", type=int, default=DEFAULT_WINDOW_HOURS)
    parser.add_argument("--half-life-hours", type=float, default=DEFAULT_HALF_LIFE_HOURS)
    parser.add_argument("--baseline-days", type=int, default=DEFAULT_BASELINE_DAYS)
    parser.add_argument("--detail", type=int, default=5, help="Cuantas entidades desglosar.")
    args = parser.parse_args()
    asyncio.run(
        preview(
            args.tenant_id,
            threshold=args.threshold,
            window_hours=args.window_hours,
            half_life_hours=args.half_life_hours,
            baseline_days=args.baseline_days,
            detail=args.detail,
        )
    )


if __name__ == "__main__":
    main()
