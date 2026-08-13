from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from cyrvanta.modules.incident.infrastructure.models import AlertReferenceModel, IncidentModel
from cyrvanta.shared.database import tenant_session

BUCKET_COUNT = 12
BUCKET_DURATION = timedelta(hours=2)
WINDOW_DURATION = timedelta(hours=24)


class StrictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ActivityTotals(StrictResponse):
    alerts: int
    incidents: int


class ActivityBucket(StrictResponse):
    bucket_start: datetime
    bucket_end: datetime
    alerts: int
    incidents: int


class OperationalActivity24h(StrictResponse):
    window_start: datetime
    window_end: datetime
    updated_at: datetime
    source_mode: Literal["EMPTY", "LIVE"]
    totals: ActivityTotals
    series: list[ActivityBucket]


def build_activity_24h(
    *,
    alert_rows: list[tuple[datetime, bool]],
    incident_rows: list[tuple[datetime, bool]],
    now: datetime,
) -> OperationalActivity24h:
    window_end = now.astimezone(UTC)
    window_start = window_end - WINDOW_DURATION
    buckets = [
        ActivityBucket(
            bucket_start=window_start + BUCKET_DURATION * index,
            bucket_end=window_start + BUCKET_DURATION * (index + 1),
            alerts=0,
            incidents=0,
        )
        for index in range(BUCKET_COUNT)
    ]
    real_activity_count = 0

    def record(rows: list[tuple[datetime, bool]], field: Literal["alerts", "incidents"]) -> None:
        nonlocal real_activity_count
        for occurred_at, is_simulated in rows:
            if is_simulated:
                continue
            normalized = occurred_at.astimezone(UTC)
            if normalized < window_start or normalized > window_end:
                continue
            index = min(
                int((normalized - window_start).total_seconds() // BUCKET_DURATION.total_seconds()),
                BUCKET_COUNT - 1,
            )
            current = buckets[index]
            buckets[index] = current.model_copy(update={field: getattr(current, field) + 1})
            real_activity_count += 1

    record(alert_rows, "alerts")
    record(incident_rows, "incidents")
    source_mode: Literal["EMPTY", "LIVE"] = "LIVE" if real_activity_count else "EMPTY"
    return OperationalActivity24h(
        window_start=window_start,
        window_end=window_end,
        updated_at=window_end,
        source_mode=source_mode,
        totals=ActivityTotals(
            alerts=sum(bucket.alerts for bucket in buckets),
            incidents=sum(bucket.incidents for bucket in buckets),
        ),
        series=buckets,
    )


class OperationalActivityService:
    async def get(self, tenant_id: UUID) -> OperationalActivity24h:
        now = datetime.now(UTC)
        window_start = now - WINDOW_DURATION
        async with tenant_session(tenant_id) as session:
            alert_rows = [
                (observed_at, is_simulated)
                for observed_at, is_simulated in (
                    await session.execute(
                        select(AlertReferenceModel.observed_at, AlertReferenceModel.is_simulated)
                        .where(
                            AlertReferenceModel.observed_at >= window_start,
                            AlertReferenceModel.observed_at <= now,
                        )
                        .order_by(AlertReferenceModel.observed_at)
                    )
                ).tuples()
            ]
            incident_rows = [
                (detected_at, is_simulated)
                for detected_at, is_simulated in (
                    await session.execute(
                        select(IncidentModel.detected_at, IncidentModel.is_simulated)
                        .where(
                            IncidentModel.detected_at >= window_start,
                            IncidentModel.detected_at <= now,
                        )
                        .order_by(IncidentModel.detected_at)
                    )
                ).tuples()
            ]
        return build_activity_24h(
            alert_rows=alert_rows,
            incident_rows=incident_rows,
            now=now,
        )
