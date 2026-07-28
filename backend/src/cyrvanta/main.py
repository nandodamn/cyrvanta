from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from cyrvanta.modules.claims.presentation.router import router as claims_router
from cyrvanta.modules.correlation.presentation.router import router as correlation_router
from cyrvanta.modules.directory.presentation.authentication_router import (
    router as directory_auth_router,
)
from cyrvanta.modules.directory.presentation.identity_link_router import (
    router as directory_link_router,
)
from cyrvanta.modules.directory.presentation.router import router as directory_router
from cyrvanta.modules.identity.presentation.administration_router import (
    router as administration_router,
)
from cyrvanta.modules.identity.presentation.router import router as auth_router
from cyrvanta.modules.incident.presentation.router import router as incident_router
from cyrvanta.modules.operations.presentation.router import router as operations_router
from cyrvanta.modules.platform.presentation.router import router as platform_router
from cyrvanta.shared.config import get_settings
from cyrvanta.shared.http import RequestContextMiddleware, install_problem_handlers
from cyrvanta.shared.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.settings = settings
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=False)
    yield
    await app.state.redis.aclose()


app = FastAPI(
    title="Cyrvanta API",
    version=settings.app_version,
    openapi_version="3.1.0",
    docs_url="/api/docs" if settings.environment != "production" else None,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-CSRF-Guard",
        "X-Request-ID",
        "X-Correlation-ID",
    ],
)
app.add_middleware(RequestContextMiddleware)
app.include_router(platform_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(administration_router, prefix="/api/v1")
app.include_router(directory_router, prefix="/api/v1")
app.include_router(directory_auth_router, prefix="/api/v1")
app.include_router(directory_link_router, prefix="/api/v1")
app.include_router(incident_router, prefix="/api/v1")
app.include_router(operations_router, prefix="/api/v1")
app.include_router(claims_router, prefix="/api/v1")
app.include_router(correlation_router, prefix="/api/v1")
install_problem_handlers(app)
