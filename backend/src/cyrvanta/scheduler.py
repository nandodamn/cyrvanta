import asyncio
import logging
import time

from cyrvanta.modules.correlation.application.entity_risk_service import sweep_all_tenants
from cyrvanta.modules.decision.application.service import DecisionService
from cyrvanta.modules.governed_memory.application.service import GovernedMemoryService
from cyrvanta.modules.integrations.application.automatic_wazuh_ingestion import (
    AutomaticWazuhIngestionService,
)
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
    decisions = DecisionService()
    memory = GovernedMemoryService()
    wazuh_ingestion = AutomaticWazuhIngestionService(settings)
    # Tracked separately from the loop interval: a sweep re-reads every alarm
    # in its window, which is far more work than the rest of this cycle and
    # does not need doing every fifteen seconds.
    last_risk_sweep = 0.0
    while True:
        logger.info("scheduler_heartbeat")
        dispatched = await dispatcher.dispatch_pending()
        if dispatched:
            logger.info("playbook_dispatch_reconciled", extra={"count": dispatched})
        timed_out = await dispatcher.reconcile_timeouts()
        if timed_out:
            logger.info("playbook_timeouts_reconciled", extra={"count": timed_out})
        try:
            synced_tenants = await wazuh_ingestion.synchronize_all_tenants()
        except Exception:
            logger.exception("wazuh_ingestion_cycle_failed")
        else:
            if synced_tenants:
                logger.info("wazuh_ingestion_cycle_completed", extra={"tenants": synced_tenants})
        expired_requests, expired_authorizations = await decisions.expire_due()
        if expired_requests or expired_authorizations:
            logger.info(
                "decision_expirations_materialized",
                extra={
                    "approval_requests": expired_requests,
                    "authorizations": expired_authorizations,
                },
            )
        if (
            settings.entity_risk_enabled
            and time.monotonic() - last_risk_sweep >= settings.entity_risk_interval_seconds
        ):
            last_risk_sweep = time.monotonic()
            try:
                risky_tenants = await sweep_all_tenants(settings)
            except Exception:
                logger.exception("entity_risk_sweep_cycle_failed")
            else:
                if risky_tenants:
                    logger.info("entity_risk_sweep_completed", extra={"tenants": risky_tenants})

        expired_memories = await memory.expire_due()
        if expired_memories:
            logger.info(
                "governed_memory_expirations_materialized",
                extra={"count": expired_memories},
            )
        # One reading a day per definition, taken here rather than computed
        # behind the screen: a metric read live changes under the reader, and
        # two people looking at the same number can then see different things.
        try:
            metric_snapshots = await memory.compute_metrics()
        except Exception:
            logger.exception("governed_memory_metrics_cycle_failed")
        else:
            if metric_snapshots:
                logger.info(
                    "governed_memory_metrics_recorded",
                    extra={"count": metric_snapshots},
                )
        # Reads the feedback ledger for patterns worth writing down and leaves
        # them as drafts. It proposes and nothing more: every suggestion still
        # needs a person to review it and a second to activate it.
        try:
            suggested = await memory.suggest_candidates()
        except Exception:
            logger.exception("governed_memory_suggestion_cycle_failed")
        else:
            if suggested:
                logger.info("governed_memory_candidates_suggested", extra={"count": suggested})
        # Detection already happened seconds ago at the manager; this interval is
        # only how long a finding waits before Cyrvanta records it, so a minute
        # was a minute of blindness during an active intrusion. Fifteen seconds
        # keeps that short without polling the indexer for nothing most cycles.
        # Removing the delay entirely needs Wazuh to push instead of Cyrvanta
        # asking -- an inbound endpoint with its own authentication, not a
        # smaller number here.
        await asyncio.sleep(settings.scheduler_interval_seconds)


if __name__ == "__main__":
    asyncio.run(run())
