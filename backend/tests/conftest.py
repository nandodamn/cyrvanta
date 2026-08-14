import os

import pytest_asyncio

os.environ.setdefault("JWT_SECRET", "test-secret-that-is-longer-than-thirty-two-characters")
os.environ.setdefault("INTEGRATION_ENCRYPTION_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")


@pytest_asyncio.fixture(autouse=True)
async def _dispose_shared_engine_pool():
    # pytest-asyncio opens a fresh event loop per test by default, but
    # cyrvanta.shared.database.engine's connection pool is a module-level
    # singleton. A connection pooled under one test's loop is unusable once
    # that loop closes, so dispose the pool after every test to force fresh
    # connections under the next test's loop.
    yield
    from cyrvanta.shared.database import engine

    await engine.dispose()
