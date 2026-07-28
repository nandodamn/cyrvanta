from __future__ import annotations

import logging
from uuid import UUID

from cyrvanta.modules.correlation.application.ports import (
    ClaimCorrelationPort,
    CorrelationRepository,
    IncidentCorrelationPort,
)
from cyrvanta.modules.correlation.domain.models import (
    MAX_RULES_PER_TRIGGER,
    CorrelationLimitExceeded,
    bucket_bounds,
    evaluate_rule,
)
from cyrvanta.shared.application.messaging import EventRecorder
from cyrvanta.shared.domain.events import DomainEvent

CORRELATION_MATCHED_EVENT = "security.correlation.matched"
CORRELATION_MEMBER_ADDED_EVENT = "security.correlation.member.added"


class CorrelationService:
    def __init__(
        self,
        repository: CorrelationRepository,
        incidents: IncidentCorrelationPort,
        claims: ClaimCorrelationPort,
        events: EventRecorder,
    ) -> None:
        self._repository = repository
        self._incidents = incidents
        self._claims = claims
        self._events = events
        self._logger = logging.getLogger("cyrvanta.correlation")

    async def handle_normalized_finding(self, event: DomainEvent) -> tuple[UUID, ...]:
        try:
            revision_id = UUID(str(event.payload["revision_id"]))
            finding_id = UUID(str(event.payload["finding_id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("normalized finding payload is invalid") from exc
        trigger = await self._repository.candidate(revision_id)
        if trigger is None or trigger.finding_id != finding_id:
            raise ValueError("normalized finding revision is unavailable")
        rules = await self._repository.active_rules()
        if len(rules) > MAX_RULES_PER_TRIGGER:
            raise CorrelationLimitExceeded("rule_limit_exceeded")
        created_ids: list[UUID] = []
        for rule in rules:
            window_start, window_end = bucket_bounds(trigger.effective_at)
            candidates = await self._repository.candidates(
                window_start, window_end, rule.max_candidates + 1
            )
            match = evaluate_rule(rule, trigger, candidates)
            if match is None:
                self._logger.info(
                    "correlation_no_match",
                    extra={
                        "tenant_id": str(event.tenant_id),
                        "rule_code": rule.code,
                        "rule_version": rule.version,
                        "candidate_count": len(candidates),
                    },
                )
                continue
            reserved = await self._repository.reserve_match(
                event.tenant_id, match, trigger.revision_id
            )
            if not reserved.created:
                self._logger.info(
                    "correlation_duplicate",
                    extra={
                        "tenant_id": str(event.tenant_id),
                        "match_id": str(reserved.match_id),
                    },
                )
                continue
            prior_incident_id = await self._repository.prior_incident(
                reserved.match_id, match
            )
            incident_result = await self._incidents.apply_match(
                tenant_id=event.tenant_id,
                match_id=reserved.match_id,
                match=match,
                prior_incident_id=prior_incident_id,
                correlation_id=event.correlation_id,
            )
            await self._repository.attach_incident(
                reserved.match_id, incident_result.incident_id
            )
            claim_id = await self._claims.record_match(
                tenant_id=event.tenant_id,
                incident_id=incident_result.incident_id,
                match_id=reserved.match_id,
                match=match,
                correlation_id=event.correlation_id,
                causation_id=event.event_id,
            )
            await self._repository.attach_claim(reserved.match_id, claim_id)
            event_name = (
                CORRELATION_MATCHED_EVENT
                if incident_result.created
                else CORRELATION_MEMBER_ADDED_EVENT
            )
            await self._events.add(
                event.create_child(
                    event_name=event_name,
                    aggregate_type="correlation_match",
                    aggregate_id=reserved.match_id,
                    producer="correlation",
                    payload={
                        "match_id": str(reserved.match_id),
                        "incident_id": str(incident_result.incident_id),
                        "rule_code": match.rule_code,
                        "rule_version": match.rule_version,
                        "score": match.score,
                        "member_count": len(match.members),
                        "schema_version": 1,
                    },
                )
            )
            created_ids.append(reserved.match_id)
        return tuple(created_ids)
