"""Publish correlation rule versions without hand-written SQL.

A rule version decides when signals become an incident, so publishing one is a
security-relevant change. Done by hand it means computing the canonical hash
correctly, retiring the previous version and inserting the new one in the same
transaction, and remembering to leave an audit trail -- each of which is silent
when it goes wrong. A rule that fails to parse does not raise anything at
publish time; it simply stops detecting.

So validation here is deliberately double: the definition is checked field by
field, and then parsed through the very same code the worker uses to load it
(`SqlCorrelationRepository._rule`). If it validates, the engine can load it.

Scope warning: `correlation_rule_versions` has no tenant_id. A rule is global,
so publishing one changes detection for every tenant, while the only roles this
system defines (`tenant-admin`, `viewer`) are tenant-scoped. `tenant_id` here
attributes the audit record; it does not scope the change.

That is why this service is reached from an operator script and not from an
HTTP endpoint: exposing it under a permission granted to `tenant-admin` would
let one tenant's administrator change detection for every other tenant, which
multitenancy isolation forbids regardless of what any later spec asks for.
Resolving it needs a decision recorded in
`docs/specifications/PLAN_AUTOMATIC_INCIDENT_DETECTION.md` (Fase 4): either
scope rules per tenant, or introduce a platform-operator role.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from cyrvanta.modules.correlation.domain.models import (
    GROUPING_KINDS,
    MAX_WINDOW_MINUTES,
    SELECTOR_FIELDS,
    WINDOW_MINUTES,
)
from cyrvanta.modules.correlation.infrastructure.models import CorrelationRuleVersionModel
from cyrvanta.modules.correlation.infrastructure.repository import SqlCorrelationRepository
from cyrvanta.modules.identity.infrastructure.models import AuditEventModel

DRAFT = "DRAFT"
ACTIVE = "ACTIVE"
RETIRED = "RETIRED"


class RuleDefinitionInvalid(Exception):
    pass


class RuleVersionNotFound(Exception):
    pass


class RuleVersionConflict(Exception):
    pass


def canonical(definition: Mapping[str, Any]) -> tuple[str, str]:
    """Serialise deterministically so the same rule always hashes the same.

    Key order must not change the hash: a definition reordered by a round trip
    through JSONB is the same rule, and a hash that disagreed would make the
    stored digest useless as an identity.
    """
    text = json.dumps(dict(definition), separators=(",", ":"), ensure_ascii=False, sort_keys=True)
    return text, sha256(text.encode("utf-8")).hexdigest()


def _positive_int(definition: Mapping[str, Any], name: str) -> None:
    if name not in definition:
        return
    value = definition[name]
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise RuleDefinitionInvalid(f"{name} must be a positive integer")


def validate_definition(definition: Any) -> None:
    """Reject a definition before anything is written.

    Every check here has a failure mode that is invisible at runtime: a rule
    with one selector can never satisfy distinct_signal_pattern, a selector on
    an unknown field silently matches nothing, and an unknown grouping would
    misgroup findings rather than error.
    """
    if not isinstance(definition, Mapping):
        raise RuleDefinitionInvalid("definition must be an object")

    selectors = definition.get("selectors")
    if not isinstance(selectors, Sequence) or isinstance(selectors, str) or not selectors:
        raise RuleDefinitionInvalid("selectors must be a non-empty list")
    codes: list[str] = []
    for selector in selectors:
        if not isinstance(selector, Mapping):
            raise RuleDefinitionInvalid("each selector must be an object")
        for key in ("code", "source_system", "field", "value"):
            if not isinstance(selector.get(key), str) or not selector[key]:
                raise RuleDefinitionInvalid(f"selector {key} must be a non-empty string")
        if selector["field"] not in SELECTOR_FIELDS:
            raise RuleDefinitionInvalid(f"selector field must be one of {sorted(SELECTOR_FIELDS)}")
        if selector["field"] == "severity" and not selector["value"].lstrip("-").isdigit():
            raise RuleDefinitionInvalid("selector severity must be an integer")
        codes.append(selector["code"])

    grouping = definition.get("grouping", "source_ip")
    if grouping not in GROUPING_KINDS:
        raise RuleDefinitionInvalid(f"grouping must be one of {sorted(GROUPING_KINDS)}")

    threshold = definition.get("threshold", 85)
    if not isinstance(threshold, int) or isinstance(threshold, bool) or not 0 <= threshold <= 100:
        raise RuleDefinitionInvalid("threshold must be an integer between 0 and 100")

    minimum = definition.get("min_severity")
    if minimum is not None:
        if not isinstance(minimum, int) or isinstance(minimum, bool) or not 0 <= minimum <= 100:
            raise RuleDefinitionInvalid("min_severity must be an integer between 0 and 100")
    elif len(set(codes)) < 2:
        # Without min_severity the engine requires distinct_signal_pattern, so
        # a rule offering one signal can never match. It would look published
        # and detect nothing.
        raise RuleDefinitionInvalid(
            "a rule without min_severity needs at least two distinct selector codes"
        )

    allowlist = definition.get("partial_issue_allowlist", [])
    if not isinstance(allowlist, Sequence) or isinstance(allowlist, str):
        raise RuleDefinitionInvalid("partial_issue_allowlist must be a list")
    if any(not isinstance(item, str) for item in allowlist):
        raise RuleDefinitionInvalid("partial_issue_allowlist must contain strings")

    for name in ("candidate_limit", "member_limit", "window_minutes"):
        _positive_int(definition, name)

    window = definition.get("window_minutes", WINDOW_MINUTES)
    if isinstance(window, int) and not isinstance(window, bool) and window > MAX_WINDOW_MINUTES:
        # An unbounded window is not a better detection, it is a slower one:
        # every trigger would scan further back until candidate_limit trips
        # and the rule raises instead of matching.
        raise RuleDefinitionInvalid(f"window_minutes must not exceed {MAX_WINDOW_MINUTES}")


def _parses_in_the_engine(rule_code: str, version: str, definition: Mapping[str, Any]) -> None:
    _text, digest = canonical(definition)
    # Built but never added to a session: this is a parse check, not a write.
    probe = CorrelationRuleVersionModel(
        rule_code=rule_code,
        version=version,
        definition=dict(definition),
        definition_sha256=digest,
    )
    try:
        SqlCorrelationRepository._rule(probe)
    except ValueError as exc:
        raise RuleDefinitionInvalid(str(exc)) from exc


class CorrelationRuleAdminService:
    """Operator-facing. Not reachable from a tenant HTTP request by design."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_versions(
        self, rule_code: str | None = None
    ) -> list[CorrelationRuleVersionModel]:
        statement = select(CorrelationRuleVersionModel)
        if rule_code is not None:
            statement = statement.where(CorrelationRuleVersionModel.rule_code == rule_code)
        rows = await self._session.scalars(
            statement.order_by(
                CorrelationRuleVersionModel.rule_code,
                CorrelationRuleVersionModel.version,
            )
        )
        return list(rows.all())

    async def create_draft(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        rule_code: str,
        version: str,
        definition: Mapping[str, Any],
    ) -> CorrelationRuleVersionModel:
        if not rule_code or not version:
            raise RuleDefinitionInvalid("rule_code and version are required")
        validate_definition(definition)
        _parses_in_the_engine(rule_code, version, definition)
        _text, digest = canonical(definition)

        existing = await self._session.scalar(
            select(CorrelationRuleVersionModel).where(
                CorrelationRuleVersionModel.rule_code == rule_code,
                CorrelationRuleVersionModel.version == version,
            )
        )
        if existing is not None:
            raise RuleVersionConflict(f"{rule_code} version {version} already exists")

        model = CorrelationRuleVersionModel(
            rule_code=rule_code,
            version=version,
            status=DRAFT,
            definition=dict(definition),
            definition_sha256=digest,
        )
        self._session.add(model)
        await self._session.flush()
        self._audit(
            tenant_id,
            actor_user_id,
            "correlation.rule.drafted",
            model,
            {"definition_sha256": digest, "grouping": definition.get("grouping", "source_ip")},
        )
        return model

    async def activate(
        self, *, tenant_id: UUID, actor_user_id: UUID, version_id: UUID
    ) -> CorrelationRuleVersionModel:
        model = await self._session.get(CorrelationRuleVersionModel, version_id)
        if model is None:
            raise RuleVersionNotFound(str(version_id))
        if model.status == ACTIVE:
            return model
        if model.status == RETIRED:
            raise RuleVersionConflict("a retired version cannot be reactivated")

        # Retiring and activating in one statement pair inside the caller's
        # transaction is what keeps the partial unique index on
        # (rule_code WHERE status='ACTIVE') satisfiable. Doing it in two
        # transactions leaves a window with no active rule, during which the
        # engine simply stops detecting that pattern.
        retired = list(
            (
                await self._session.scalars(
                    select(CorrelationRuleVersionModel).where(
                        CorrelationRuleVersionModel.rule_code == model.rule_code,
                        CorrelationRuleVersionModel.status == ACTIVE,
                    )
                )
            ).all()
        )
        await self._session.execute(
            update(CorrelationRuleVersionModel)
            .where(
                CorrelationRuleVersionModel.rule_code == model.rule_code,
                CorrelationRuleVersionModel.status == ACTIVE,
            )
            .values(status=RETIRED)
        )
        model.status = ACTIVE
        await self._session.flush()
        self._audit(
            tenant_id,
            actor_user_id,
            "correlation.rule.activated",
            model,
            {
                "definition_sha256": model.definition_sha256,
                "retired": [row.version for row in retired],
                "scope": "global",
            },
        )
        return model

    async def retire(
        self, *, tenant_id: UUID, actor_user_id: UUID, version_id: UUID
    ) -> CorrelationRuleVersionModel:
        model = await self._session.get(CorrelationRuleVersionModel, version_id)
        if model is None:
            raise RuleVersionNotFound(str(version_id))
        if model.status == RETIRED:
            return model
        model.status = RETIRED
        await self._session.flush()
        self._audit(
            tenant_id,
            actor_user_id,
            "correlation.rule.retired",
            model,
            {"definition_sha256": model.definition_sha256, "scope": "global"},
        )
        return model

    def _audit(
        self,
        tenant_id: UUID,
        actor_user_id: UUID,
        action: str,
        model: CorrelationRuleVersionModel,
        details: dict[str, Any],
    ) -> None:
        self._session.add(
            AuditEventModel(
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                action=action,
                resource_type="correlation_rule_version",
                resource_id=model.id,
                correlation_id=uuid4(),
                outcome="success",
                details={"rule_code": model.rule_code, "version": model.version, **details},
            )
        )
