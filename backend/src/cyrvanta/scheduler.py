import asyncio
import logging

from cyrvanta.modules.governed_memory.application.service import GovernedMemoryService
from cyrvanta.modules.playbooks.infrastructure.hybrid_dispatcher import (
    HybridPlaybookDispatcher,
)
from cyrvanta.shared.config import get_settings
from cyrvanta.shared.logging import configure_logging


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger("cyrvanta.scheduler")
    dispatcher = HybridPlaybookDispatcher(settings)
    memory = GovernedMemoryService()
    while True:
        logger.info("scheduler_heartbeat")
        dispatched = await dispatcher.dispatch_pending()
        if dispatched:
            logger.info("playbook_dispatch_reconciled", extra={"count": dispatched})
        timed_out = await dispatcher.reconcile_timeouts()
        if timed_out:
            logger.info("playbook_timeouts_reconciled", extra={"count": timed_out})
        expired_memories = await memory.expire_due()
        if expired_memories:
            logger.info(
                "governed_memory_expirations_materialized",
                extra={"count": expired_memories},
            )
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(run())
