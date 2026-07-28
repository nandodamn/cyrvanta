import os

os.environ.setdefault("JWT_SECRET", "test-secret-that-is-longer-than-thirty-two-characters")
os.environ.setdefault("INTEGRATION_ENCRYPTION_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
