from typing import Any

import aio_pika
from fastapi import APIRouter, Request
from sqlalchemy import text

from cyrvanta import __version__
from cyrvanta.shared.database import engine

router = APIRouter(tags=["platform"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/version")
async def version() -> dict[str, str]:
    return {"version": __version__}


@router.get("/ready")
async def ready(request: Request) -> dict[str, Any]:
    checks: dict[str, str] = {}
    try:
        async with engine.connect() as db_connection:
            await db_connection.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:
        checks["postgres"] = "unavailable"
    try:
        checks["redis"] = "ok" if await request.app.state.redis.ping() else "unavailable"
    except Exception:
        checks["redis"] = "unavailable"
    try:
        rmq_connection = await aio_pika.connect_robust(request.app.state.settings.rabbitmq_url)
        await rmq_connection.close()
        checks["rabbitmq"] = "ok"
    except Exception:
        checks["rabbitmq"] = "unavailable"
    status_value = "ready" if all(value == "ok" for value in checks.values()) else "degraded"
    return {"status": status_value, "checks": checks}
