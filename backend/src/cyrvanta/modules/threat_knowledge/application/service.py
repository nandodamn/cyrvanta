from __future__ import annotations

import json
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cyrvanta.modules.ai_analysis.application.ports import ExplanationDraft
from cyrvanta.modules.correlation.infrastructure.models import CorrelationMemberModel
from cyrvanta.modules.incident.infrastructure.models import CorrelationRunModel, IncidentModel
from cyrvanta.modules.integrations.infrastructure.models import FindingRevisionModel
from cyrvanta.modules.risk.domain.models import RiskInput, assess_risk, deterministic_explanation
from cyrvanta.modules.threat_knowledge.application.schemas import (
    EnrichmentResponse,
    ExplanationResponse,
    RiskAssessmentResponse,
    RiskFactorResponse,
    ThreatMappingResponse,
)
from cyrvanta.modules.threat_knowledge.domain.models import map_credential_attack
from cyrvanta.modules.threat_knowledge.infrastructure.models import (
    AttackMappingEvidenceModel,
    AttackObjectModel,
    AttackReleaseModel,
    IncidentAttackMappingModel,
    IncidentExplanationModel,
    RiskAssessmentModel,
    RiskDefinitionModel,
    RiskFactorModel,
    ThreatMappingRuleModel,
)
from cyrvanta.shared.application.messaging import EventRecorder
from cyrvanta.shared.domain.events import DomainEvent

THREAT_MAPPING_ASSESSED_EVENT = "security.threat_mapping.assessed"
RISK_ASSESSED_EVENT = "security.risk.assessed"
EXPLANATION_GENERATED_EVENT = "security.explanation.generated"
EXPLANATION_FAILED_EVENT = "security.explanation.failed"


class EnrichmentUnavailable(ValueError):
    pass


class ThreatEnrichmentService:
    def __init__(self, session: AsyncSession, events: EventRecorder) -> None:
        self._session = session
        self._events = events

    async def enrich(
        self,
        tenant_id: UUID,
        incident_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> EnrichmentResponse:
        incident = await self._session.scalar(
            select(IncidentModel).where(
                IncidentModel.id == incident_id,
                IncidentModel.is_simulated.is_(False),
            )
        )
        if incident is None:
            raise EnrichmentUnavailable("incident not found")
        run = await self._session.scalar(
            select(CorrelationRunModel)
            .where(
                CorrelationRunModel.incident_id == incident_id,
                CorrelationRunModel.is_simulated.is_(False),
                CorrelationRunModel.result_type == "MATCHED",
            )
            .order_by(CorrelationRunModel.created_at.desc())
            .limit(1)
        )
        if run is None:
            raise EnrichmentUnavailable("incident has no deterministic correlation")
        release = await self._session.scalar(
            select(AttackReleaseModel)
            .where(
                AttackReleaseModel.domain == "enterprise-attack",
                AttackReleaseModel.status == "ACTIVE",
            )
            .limit(1)
        )
        if release is None:
            raise EnrichmentUnavailable("no active ATT&CK release")
        rule = await self._session.scalar(
            select(ThreatMappingRuleModel)
            .where(
                ThreatMappingRuleModel.rule_code == "credential-attack",
                ThreatMappingRuleModel.version == "2",
                ThreatMappingRuleModel.status == "ACTIVE",
            )
            .limit(1)
        )
        definition = await self._session.scalar(
            select(RiskDefinitionModel)
            .where(
                RiskDefinitionModel.code == "incident-risk",
                RiskDefinitionModel.version == "1",
                RiskDefinitionModel.status == "ACTIVE",
            )
            .limit(1)
        )
        if rule is None or definition is None:
            raise EnrichmentUnavailable("enrichment definitions are unavailable")
        members = list(
            (
                await self._session.scalars(
                    select(CorrelationMemberModel)
                    .where(CorrelationMemberModel.correlation_run_id == run.id)
                    .order_by(CorrelationMemberModel.sort_order)
                )
            ).all()
        )
        if not members:
            raise EnrichmentUnavailable("correlation has no evidence")
        revision_ids = [item.revision_id for item in members]
        revisions = list(
            (
                await self._session.scalars(
                    select(FindingRevisionModel).where(FindingRevisionModel.id.in_(revision_ids))
                )
            ).all()
        )
        candidates = map_credential_attack(
            run.rule_code, run.rule_version, tuple(item.selector_code for item in members)
        )
        mappings: list[IncidentAttackMappingModel] = []
        for candidate in candidates:
            attack_object = await self._session.scalar(
                select(AttackObjectModel).where(
                    AttackObjectModel.release_id == release.id,
                    AttackObjectModel.external_id == candidate.technique_external_id,
                    AttackObjectModel.object_type == "attack-pattern",
                    AttackObjectModel.revoked.is_(False),
                    AttackObjectModel.deprecated.is_(False),
                )
            )
            if attack_object is None:
                raise EnrichmentUnavailable(
                    f"active ATT&CK release lacks {candidate.technique_external_id}"
                )
            fingerprint = self._fingerprint(
                tenant_id, incident_id, run.id, rule.id, attack_object.id, candidate.selector_codes
            )
            mapping = await self._session.scalar(
                select(IncidentAttackMappingModel).where(
                    IncidentAttackMappingModel.tenant_id == tenant_id,
                    IncidentAttackMappingModel.fingerprint == fingerprint,
                )
            )
            if mapping is None:
                mapping = IncidentAttackMappingModel(
                    tenant_id=tenant_id,
                    incident_id=incident_id,
                    attack_object_id=attack_object.id,
                    mapping_rule_id=rule.id,
                    correlation_run_id=run.id,
                    status="SUPPORTED",
                    selector_codes=list(candidate.selector_codes),
                    fingerprint=fingerprint,
                )
                self._session.add(mapping)
                await self._session.flush()
                self._session.add(
                    AttackMappingEvidenceModel(
                        tenant_id=tenant_id,
                        mapping_id=mapping.id,
                        evidence_type="CORRELATION_MATCH",
                        correlation_run_id=run.id,
                        sort_order=0,
                    )
                )
                for index, member in enumerate(members, start=1):
                    if member.selector_code in candidate.selector_codes:
                        self._session.add(
                            AttackMappingEvidenceModel(
                                tenant_id=tenant_id,
                                mapping_id=mapping.id,
                                evidence_type="FINDING_REVISION",
                                finding_revision_id=member.revision_id,
                                sort_order=index,
                            )
                        )
                await self._events.add(
                    DomainEvent.create(
                        event_name=THREAT_MAPPING_ASSESSED_EVENT,
                        tenant_id=tenant_id,
                        aggregate_type="threat_mapping",
                        aggregate_id=mapping.id,
                        correlation_id=correlation_id,
                        causation_id=causation_id,
                        producer="threat-knowledge",
                        payload={
                            "mapping_id": str(mapping.id),
                            "incident_id": str(incident_id),
                            "technique_external_id": candidate.technique_external_id,
                            "status": "SUPPORTED",
                            "schema_version": 1,
                        },
                    )
                )
            mappings.append(mapping)
        risk_input = RiskInput(
            severity=incident.severity,
            evidence_count=len(revisions),
            source_count=len({item.source_system for item in revisions}),
            supported_mapping_count=len(mappings),
            normalization_statuses=tuple(item.normalization_status for item in revisions),
        )
        risk = assess_risk(risk_input)
        assessment = await self._session.scalar(
            select(RiskAssessmentModel).where(
                RiskAssessmentModel.tenant_id == tenant_id,
                RiskAssessmentModel.incident_id == incident_id,
                RiskAssessmentModel.fingerprint == risk.fingerprint,
            )
        )
        if assessment is None:
            assessment = RiskAssessmentModel(
                tenant_id=tenant_id,
                incident_id=incident_id,
                definition_id=definition.id,
                correlation_run_id=run.id,
                score=risk.score,
                band=risk.band,
                input_snapshot={
                    "severity": risk_input.severity,
                    "evidence_count": risk_input.evidence_count,
                    "source_count": risk_input.source_count,
                    "supported_mapping_count": risk_input.supported_mapping_count,
                    "normalization_statuses": list(risk_input.normalization_statuses),
                },
                fingerprint=risk.fingerprint,
            )
            self._session.add(assessment)
            await self._session.flush()
            for factor in risk.factors:
                self._session.add(
                    RiskFactorModel(
                        tenant_id=tenant_id,
                        assessment_id=assessment.id,
                        factor_code=factor.code,
                        weight=factor.weight,
                        contribution=factor.contribution,
                        evidence_snapshot={"revision_ids": [str(item) for item in revision_ids]},
                    )
                )
            await self._events.add(
                DomainEvent.create(
                    event_name=RISK_ASSESSED_EVENT,
                    tenant_id=tenant_id,
                    aggregate_type="risk_assessment",
                    aggregate_id=assessment.id,
                    correlation_id=correlation_id,
                    causation_id=causation_id,
                    producer="risk",
                    payload={
                        "assessment_id": str(assessment.id),
                        "incident_id": str(incident_id),
                        "score": risk.score,
                        "band": risk.band,
                        "schema_version": 1,
                    },
                )
            )
        technique_ids = tuple(item.technique_external_id for item in candidates)
        explanation_es, explanation_en = deterministic_explanation(risk, technique_ids)
        explanations: list[IncidentExplanationModel] = []
        for locale, text in (("es", explanation_es), ("en", explanation_en)):
            explanation = await self._session.scalar(
                select(IncidentExplanationModel).where(
                    IncidentExplanationModel.tenant_id == tenant_id,
                    IncidentExplanationModel.risk_assessment_id == assessment.id,
                    IncidentExplanationModel.locale == locale,
                    IncidentExplanationModel.mode == "DETERMINISTIC",
                )
            )
            if explanation is None:
                explanation = IncidentExplanationModel(
                    tenant_id=tenant_id,
                    incident_id=incident_id,
                    risk_assessment_id=assessment.id,
                    locale=locale,
                    mode="DETERMINISTIC",
                    provider="template-v1",
                    model=None,
                    text=text,
                    grounded=True,
                    input_fingerprint=risk.fingerprint,
                )
                self._session.add(explanation)
                await self._session.flush()
                await self._events.add(
                    DomainEvent.create(
                        event_name=EXPLANATION_GENERATED_EVENT,
                        tenant_id=tenant_id,
                        aggregate_type="incident_explanation",
                        aggregate_id=explanation.id,
                        correlation_id=correlation_id,
                        causation_id=causation_id,
                        producer="risk",
                        payload={
                            "explanation_id": str(explanation.id),
                            "incident_id": str(incident_id),
                            "locale": locale,
                            "mode": "DETERMINISTIC",
                            "schema_version": 1,
                        },
                    )
                )
            explanations.append(explanation)
        await self._session.flush()
        return await self.get(tenant_id, incident_id, assessment.id)

    async def get(
        self, tenant_id: UUID, incident_id: UUID, assessment_id: UUID | None = None
    ) -> EnrichmentResponse:
        assessment = await self._session.scalar(
            select(RiskAssessmentModel)
            .where(
                RiskAssessmentModel.tenant_id == tenant_id,
                RiskAssessmentModel.incident_id == incident_id,
                *((RiskAssessmentModel.id == assessment_id,) if assessment_id is not None else ()),
            )
            .order_by(RiskAssessmentModel.created_at.desc())
            .limit(1)
        )
        if assessment is None:
            raise EnrichmentUnavailable("incident has no risk assessment")
        definition = await self._session.get(RiskDefinitionModel, assessment.definition_id)
        factor_rows = list(
            (
                await self._session.scalars(
                    select(RiskFactorModel)
                    .where(RiskFactorModel.assessment_id == assessment.id)
                    .order_by(RiskFactorModel.factor_code)
                )
            ).all()
        )
        mapping_rows = (
            await self._session.execute(
                select(IncidentAttackMappingModel, AttackObjectModel)
                .join(
                    AttackObjectModel,
                    AttackObjectModel.id == IncidentAttackMappingModel.attack_object_id,
                )
                .where(
                    IncidentAttackMappingModel.tenant_id == tenant_id,
                    IncidentAttackMappingModel.incident_id == incident_id,
                    IncidentAttackMappingModel.correlation_run_id == assessment.correlation_run_id,
                )
                .order_by(AttackObjectModel.external_id)
            )
        ).all()
        evidence_rows = list(
            (
                await self._session.scalars(
                    select(AttackMappingEvidenceModel).where(
                        AttackMappingEvidenceModel.mapping_id.in_(
                            [mapping.id for mapping, _ in mapping_rows]
                        )
                    )
                )
            ).all()
        )
        explanations = list(
            (
                await self._session.scalars(
                    select(IncidentExplanationModel)
                    .where(IncidentExplanationModel.risk_assessment_id == assessment.id)
                    .order_by(IncidentExplanationModel.locale)
                )
            ).all()
        )
        return EnrichmentResponse(
            mappings=[
                ThreatMappingResponse(
                    id=mapping.id,
                    incident_id=mapping.incident_id,
                    correlation_run_id=mapping.correlation_run_id,
                    external_id=attack.external_id or "",
                    name_en=attack.name_en or "",
                    tactic_codes=list(attack.tactic_codes),
                    status=mapping.status,
                    selector_codes=list(mapping.selector_codes),
                    evidence_revision_ids=[
                        item.finding_revision_id
                        for item in evidence_rows
                        if item.mapping_id == mapping.id and item.finding_revision_id is not None
                    ],
                    created_at=mapping.created_at,
                )
                for mapping, attack in mapping_rows
            ],
            risk=RiskAssessmentResponse(
                id=assessment.id,
                incident_id=assessment.incident_id,
                definition_code=definition.code if definition else "incident-risk",
                definition_version=definition.version if definition else "1",
                score=assessment.score,
                band=assessment.band,
                fingerprint=assessment.fingerprint,
                factors=[
                    RiskFactorResponse(
                        code=item.factor_code,
                        weight=item.weight,
                        contribution=item.contribution,
                    )
                    for item in factor_rows
                ],
                created_at=assessment.created_at,
            ),
            explanations=[
                ExplanationResponse(
                    id=item.id,
                    incident_id=item.incident_id,
                    risk_assessment_id=item.risk_assessment_id,
                    locale=item.locale,
                    mode=item.mode,
                    provider=item.provider,
                    text=item.text,
                    grounded=item.grounded,
                    created_at=item.created_at,
                )
                for item in explanations
            ],
        )

    async def record_ai_redaction(
        self,
        tenant_id: UUID,
        incident_id: UUID,
        assessment_id: UUID,
        correlation_id: UUID,
        draft: ExplanationDraft | None,
    ) -> None:
        assessment = await self._session.scalar(
            select(RiskAssessmentModel).where(
                RiskAssessmentModel.id == assessment_id,
                RiskAssessmentModel.incident_id == incident_id,
            )
        )
        if assessment is None:
            raise EnrichmentUnavailable("risk assessment not found")
        if draft is None:
            await self._events.add(
                DomainEvent.create(
                    event_name=EXPLANATION_FAILED_EVENT,
                    tenant_id=tenant_id,
                    aggregate_type="risk_assessment",
                    aggregate_id=assessment.id,
                    correlation_id=correlation_id,
                    producer="ai-analysis",
                    payload={
                        "assessment_id": str(assessment.id),
                        "incident_id": str(incident_id),
                        "error_code": "provider_unavailable_or_invalid",
                        "fallback": "DETERMINISTIC",
                        "schema_version": 1,
                    },
                )
            )
            return
        for locale, text in (("es", draft.text_es), ("en", draft.text_en)):
            existing = await self._session.scalar(
                select(IncidentExplanationModel.id).where(
                    IncidentExplanationModel.risk_assessment_id == assessment.id,
                    IncidentExplanationModel.locale == locale,
                    IncidentExplanationModel.mode == "AI_REDACTION",
                )
            )
            if existing is not None:
                continue
            explanation = IncidentExplanationModel(
                tenant_id=tenant_id,
                incident_id=incident_id,
                risk_assessment_id=assessment.id,
                locale=locale,
                mode="AI_REDACTION",
                provider=draft.provider,
                model=draft.model,
                text=text,
                grounded=True,
                input_fingerprint=assessment.fingerprint,
            )
            self._session.add(explanation)
            await self._session.flush()
            await self._events.add(
                DomainEvent.create(
                    event_name=EXPLANATION_GENERATED_EVENT,
                    tenant_id=tenant_id,
                    aggregate_type="incident_explanation",
                    aggregate_id=explanation.id,
                    correlation_id=correlation_id,
                    producer="ai-analysis",
                    payload={
                        "explanation_id": str(explanation.id),
                        "incident_id": str(incident_id),
                        "locale": locale,
                        "mode": "AI_REDACTION",
                        "schema_version": 1,
                    },
                )
            )

    @staticmethod
    def _fingerprint(
        tenant_id: UUID,
        incident_id: UUID,
        run_id: UUID,
        rule_id: UUID,
        attack_object_id: UUID,
        selectors: tuple[str, ...],
    ) -> str:
        material = {
            "tenant_id": str(tenant_id),
            "incident_id": str(incident_id),
            "correlation_run_id": str(run_id),
            "mapping_rule_id": str(rule_id),
            "attack_object_id": str(attack_object_id),
            "selectors": sorted(selectors),
        }
        return sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
