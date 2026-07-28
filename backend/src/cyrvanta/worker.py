import asyncio
import logging

import aio_pika

from cyrvanta.shared.config import get_settings
from cyrvanta.shared.logging import configure_logging


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger("cyrvanta.worker")
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    logger.info("worker_ready")
    try:
        await asyncio.Future()
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(run())
