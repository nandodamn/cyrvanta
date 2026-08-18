from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from cyrvanta.modules.correlation.application.ports import ReservedMatch
from cyrvanta.modules.correlation.domain.models import (
    ACTIVE_INCIDENT_STATES,
    GROUPING_KINDS,
    CorrelationCandidate,
    CorrelationMatch,
    CorrelationRule,
    EntityReference,
    SignalSelector,
)
from cyrvanta.modules.correlation.infrastructure.models import (
    CorrelationFactorModel,
    CorrelationMemberModel,
    CorrelationRuleVersionModel,
)
from cyrvanta.modules.incident.infrastructure.models import (
    AlertReferenceModel,
    CorrelationRunModel,
    IncidentModel,
)
from cyrvanta.modules.integrations.infrastructure.models import FindingRevisionModel


class SqlCorrelationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def active_rules(self) -> tuple[CorrelationRule, ...]:
        models = (
            await self._session.scalars(
                select(CorrelationRuleVersionModel)
                .where(CorrelationRuleVersionModel.status == "ACTIVE")
                .order_by(
                    CorrelationRuleVersionModel.rule_code,
                    CorrelationRuleVersionModel.version,
                )
            )
        ).all()
        return tuple(self._rule(model) for model in models)

    async def candidate(self, revision_id: UUID) -> CorrelationCandidate | None:
        row = (
            await self._session.execute(
                select(FindingRevisionModel, AlertReferenceModel.is_simulated)
                .join(
                    AlertReferenceModel,
                    AlertReferenceModel.id == FindingRevisionModel.alert_reference_id,
                )
                .where(FindingRevisionModel.id == revision_id)
                .limit(1)
            )
        ).one_or_none()
        return self._candidate(*row) if row is not None else None

    async def candidates(
        self, window_start: datetime, window_end: datetime, limit: int
    ) -> tuple[CorrelationCandidate, ...]:
        rows = (
            await self._session.execute(
                select(FindingRevisionModel, AlertReferenceModel.is_simulated)
                .join(
                    AlertReferenceModel,
                    AlertReferenceModel.id == FindingRevisionModel.alert_reference_id,
                )
                .where(FindingRevisionModel.effective_at >= window_start)
                .where(FindingRevisionModel.effective_at < window_end)
                .order_by(
                    FindingRevisionModel.effective_at,
                    FindingRevisionModel.alert_reference_id,
                    FindingRevisionModel.id,
                )
                .limit(limit)
            )
        ).all()
        return tuple(self._candidate(model, simulated) for model, simulated in rows)

    async def reserve_match(
        self,
        tenant_id: UUID,
        match: CorrelationMatch,
        trigger_revision_id: UUID,
    ) -> ReservedMatch:
        match_id = uuid4()
        explanation = (
            f"rule={match.rule_code};version={match.rule_version};"
            f"score={match.score};members={len(match.members)}"
        )
        inserted_id = await self._session.scalar(
            pg_insert(CorrelationRunModel)
            .values(
                id=match_id,
                tenant_id=tenant_id,
                incident_id=None,
                rule_code=match.rule_code,
                rule_version=match.rule_version,
                rule_definition_sha256=match.rule_definition_sha256,
                grouping_key_hash=match.grouping_key_hash,
                score=match.score,
                threshold=match.threshold,
                window_start=match.window_start,
                window_end=match.window_end,
                claim_id=None,
                result_type="MATCHED",
                schema_version=1,
                explanation=explanation,
                input_fingerprint=match.input_fingerprint,
                is_simulated=match.is_simulated,
            )
            .on_conflict_do_nothing(
                index_elements=(
                    CorrelationRunModel.tenant_id,
                    CorrelationRunModel.rule_code,
                    CorrelationRunModel.rule_version,
                    CorrelationRunModel.input_fingerprint,
                )
            )
            .returning(CorrelationRunModel.id)
        )
        if not isinstance(inserted_id, UUID):
            existing_id = await self._session.scalar(
                select(CorrelationRunModel.id).where(
                    CorrelationRunModel.rule_code == match.rule_code,
                    CorrelationRunModel.rule_version == match.rule_version,
                    CorrelationRunModel.input_fingerprint == match.input_fingerprint,
                )
            )
            if not isinstance(existing_id, UUID):
                raise RuntimeError("correlation idempotency reservation failed")
            return ReservedMatch(existing_id, False)
        for order, member in enumerate(match.members):
            self._session.add(
                CorrelationMemberModel(
                    tenant_id=tenant_id,
                    correlation_run_id=inserted_id,
                    finding_id=member.finding_id,
                    revision_id=member.revision_id,
                    role=("TRIGGER" if member.revision_id == trigger_revision_id else "SUPPORTING"),
                    sort_order=order,
                    selector_code=match.selector_codes[member.revision_id],
                    effective_at=member.effective_at,
                    integration_id=member.integration_id,
                    source_system=member.source_system,
                    is_simulated=member.is_simulated,
                )
            )
        for factor in match.factors:
            self._session.add(
                CorrelationFactorModel(
                    tenant_id=tenant_id,
                    correlation_run_id=inserted_id,
                    factor_code=factor.code,
                    matched=factor.matched,
                    weight=factor.weight,
                    contribution=factor.contribution,
                    evidence_revision_ids=list(factor.evidence_revision_ids),
                    explanation_code=factor.explanation_code,
                )
            )
        await self._session.flush()
        return ReservedMatch(inserted_id, True)

    async def prior_incident(self, match_id: UUID, match: CorrelationMatch) -> UUID | None:
        return await self._session.scalar(
            select(CorrelationRunModel.incident_id)
            .join(IncidentModel, IncidentModel.id == CorrelationRunModel.incident_id)
            .where(
                CorrelationRunModel.id != match_id,
                CorrelationRunModel.rule_code == match.rule_code,
                CorrelationRunModel.rule_version == match.rule_version,
                CorrelationRunModel.grouping_key_hash == match.grouping_key_hash,
                CorrelationRunModel.incident_id.is_not(None),
                IncidentModel.status.in_(ACTIVE_INCIDENT_STATES),
            )
            .order_by(CorrelationRunModel.created_at.desc(), CorrelationRunModel.id.desc())
            .limit(1)
        )

    async def attach_incident(self, match_id: UUID, incident_id: UUID) -> None:
        model = await self._session.get(CorrelationRunModel, match_id)
        if model is None:
            raise RuntimeError("correlation match is unavailable")
        model.incident_id = incident_id
        await self._session.flush()

    async def attach_claim(self, match_id: UUID, claim_id: UUID) -> None:
        model = await self._session.get(CorrelationRunModel, match_id)
        if model is None:
            raise RuntimeError("correlation match is unavailable")
        model.claim_id = claim_id
        await self._session.flush()

    @staticmethod
    def _rule(model: CorrelationRuleVersionModel) -> CorrelationRule:
        definition = model.definition
        raw_selectors = definition.get("selectors")
        if not isinstance(raw_selectors, list):
            raise ValueError("correlation rule selectors are invalid")
        selectors = tuple(
            SignalSelector(
                code=str(item["code"]),
                source_system=str(item["source_system"]),
                field=str(item["field"]),
                value=str(item["value"]),
            )
            for item in raw_selectors
            if isinstance(item, dict)
        )
        allowlist = definition.get("partial_issue_allowlist", [])
        if not isinstance(allowlist, list):
            raise ValueError("correlation partial allowlist is invalid")

        def integer(name: str, default: int) -> int:
            value = definition.get(name, default)
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"correlation rule {name} is invalid")
            return value

        # Absent means source_ip: every rule persisted before this key existed
        # is read back with the grouping it already assumed. A present but
        # unrecognised value fails loudly rather than silently falling back,
        # since it would otherwise misgroup findings without warning.
        grouping = definition.get("grouping", "source_ip")
        if not isinstance(grouping, str) or grouping not in GROUPING_KINDS:
            raise ValueError("correlation rule grouping is invalid")

        return CorrelationRule(
            code=model.rule_code,
            version=model.version,
            definition_sha256=model.definition_sha256,
            selectors=selectors,
            partial_issue_allowlist=frozenset(str(item) for item in allowlist),
            threshold=integer("threshold", 85),
            max_candidates=integer("candidate_limit", 500),
            max_members=integer("member_limit", 32),
            grouping=grouping,
        )

    @staticmethod
    def _candidate(model: FindingRevisionModel, is_simulated: bool) -> CorrelationCandidate:
        entities: list[EntityReference] = []
        for item in model.entity_references:
            if not isinstance(item, dict):
                continue
            kind = item.get("kind")
            value = item.get("value")
            namespace = item.get("namespace")
            if isinstance(kind, str) and isinstance(value, str):
                entities.append(
                    EntityReference(
                        kind=kind,
                        value=value,
                        namespace=namespace if isinstance(namespace, str) else None,
                    )
                )
        return CorrelationCandidate(
            finding_id=model.alert_reference_id,
            revision_id=model.id,
            integration_id=model.integration_id,
            source_system=model.source_system,
            effective_at=model.effective_at,
            effective_time_basis=model.effective_time_basis,
            severity_score=model.severity_score,
            category=model.category,
            rule_reference=model.rule_reference,
            normalization_status=model.normalization_status,
            issue_codes=tuple(model.issue_codes),
            entities=tuple(entities),
            is_simulated=is_simulated,
        )
