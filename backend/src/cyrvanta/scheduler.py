import asyncio
import logging

from cyrvanta.shared.config import get_settings
from cyrvanta.shared.logging import configure_logging


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger("cyrvanta.scheduler")
    while True:
        logger.info("scheduler_heartbeat")
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(run())
