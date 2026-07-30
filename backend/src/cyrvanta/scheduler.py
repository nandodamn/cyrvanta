import asyncio
import logging

from cyrvanta.modules.playbooks.infrastructure.dispatcher import N8nPlaybookDispatcher
from cyrvanta.shared.config import get_settings
from cyrvanta.shared.logging import configure_logging


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger("cyrvanta.scheduler")
    dispatcher = N8nPlaybookDispatcher(settings)
    while True:
        logger.info("scheduler_heartbeat")
        dispatched = await dispatcher.dispatch_pending()
        if dispatched:
            logger.info("playbook_dispatch_reconciled", extra={"count": dispatched})
        timed_out = await dispatcher.reconcile_timeouts()
        if timed_out:
            logger.info("playbook_timeouts_reconciled", extra={"count": timed_out})
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(run())
