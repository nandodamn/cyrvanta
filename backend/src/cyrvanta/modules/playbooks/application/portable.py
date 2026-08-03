from __future__ import annotations

import hashlib
import json
import re
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

CODE_PATTERN = r"^[a-z][a-z0-9-]{2,63}$"
IDENTIFIER_PATTERN = r"^[a-z][a-z0-9_-]{0,63}$"
SEMVER_PATTERN = r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$"
SCHEMA_REF_PATTERN = r"^[a-z0-9][a-z0-9._/-]{0,127}$"
PATH_PATTERN = (
    r"^(?:input|steps\.[a-z][a-z0-9_-]{0,63}\.output)"
    r"(?:\.[A-Za-z][A-Za-z0-9_-]{0,63}){0,8}$"
)
SENSITIVE_KEY = re.compile(r"(?:password|secret|token|api[_-]?key|credential)", re.IGNORECASE)
STEP_OUTPUT_PATH = re.compile(r"^steps\.([a-z][a-z0-9_-]{0,63})\.output(?:\.|$)")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class LocalizedTitle(StrictModel):
    es: str = Field(min_length=1, max_length=120)
    en: str = Field(min_length=1, max_length=120)


class LocalizedDescription(StrictModel):
    es: str = Field(min_length=1, max_length=1000)
    en: str = Field(min_length=1, max_length=1000)


class PlaybookTimeouts(StrictModel):
    overall_seconds: int = Field(ge=1, le=900)
    action_seconds: int = Field(ge=1, le=300)
    max_attempts: int = Field(default=1, ge=1, le=3)

    @model_validator(mode="after")
    def action_fits_overall_deadline(self) -> Self:
        if self.action_seconds > self.overall_seconds:
            raise ValueError("action_seconds cannot exceed overall_seconds")
        return self


class ConditionExpression(StrictModel):
    operator: Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "exists", "and", "or", "not"]
    path: str | None = Field(default=None, pattern=PATH_PATTERN)
    value: JsonValue = None
    operands: list[ConditionExpression] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_operator_shape(self) -> Self:
        fields = self.model_fields_set
        if self.operator in {"eq", "ne", "gt", "gte", "lt", "lte", "in"}:
            if self.path is None or "value" not in fields or self.operands:
                raise ValueError("comparison expressions require path and value only")
        elif self.operator == "exists":
            if self.path is None or "value" in fields or self.operands:
                raise ValueError("exists expressions require path only")
        elif self.operator in {"and", "or"}:
            if self.path is not None or "value" in fields or not 2 <= len(self.operands) <= 8:
                raise ValueError("and/or expressions require 2-8 operands only")
        elif self.path is not None or "value" in fields or len(self.operands) != 1:
            raise ValueError("not expressions require exactly one operand")
        return self


class ActionStep(StrictModel):
    id: str = Field(pattern=IDENTIFIER_PATTERN)
    type: Literal["ACTION"]
    action: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,95}$")
    action_version: str = Field(pattern=SEMVER_PATTERN)
    parameters: dict[str, JsonValue] = Field(default_factory=dict, max_length=64)
    credential_aliases: list[str] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def validate_parameters_and_aliases(self) -> Self:
        _reject_sensitive_keys(self.parameters)
        if len(set(self.credential_aliases)) != len(self.credential_aliases):
            raise ValueError("credential aliases must be unique")
        for alias in self.credential_aliases:
            if re.fullmatch(IDENTIFIER_PATTERN, alias) is None:
                raise ValueError("credential alias is invalid")
        return self


class ConditionStep(StrictModel):
    id: str = Field(pattern=IDENTIFIER_PATTERN)
    type: Literal["CONDITION"]
    expression: ConditionExpression


PortableStep = Annotated[ActionStep | ConditionStep, Field(discriminator="type")]


class PlaybookEdge(StrictModel):
    from_step: str = Field(pattern=IDENTIFIER_PATTERN)
    to_step: str = Field(pattern=IDENTIFIER_PATTERN)
    outcome: Literal["SUCCESS", "FAILURE", "TRUE", "FALSE", "ALWAYS"]


class PortablePlaybookV1(StrictModel):
    schema_version: Literal["1.0"]
    code: str = Field(pattern=CODE_PATTERN)
    version: str = Field(pattern=SEMVER_PATTERN)
    title_i18n: LocalizedTitle
    description_i18n: LocalizedDescription
    trigger_contract: str | None = Field(default=None, pattern=SCHEMA_REF_PATTERN)
    execution_mode: Literal["SIMULATED", "LIVE"]
    impact_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    input_schema_ref: str = Field(pattern=SCHEMA_REF_PATTERN)
    result_schema_ref: str = Field(pattern=SCHEMA_REF_PATTERN)
    steps: list[PortableStep] = Field(min_length=1, max_length=64)
    edges: list[PlaybookEdge] = Field(default_factory=list, max_length=128)
    timeouts: PlaybookTimeouts
    credential_aliases: list[str] = Field(default_factory=list, max_length=32)
    labels: dict[str, str] = Field(default_factory=dict, max_length=32)

    @model_validator(mode="after")
    def validate_graph_and_limits(self) -> Self:
        step_ids = [step.id for step in self.steps]
        if len(set(step_ids)) != len(step_ids):
            raise ValueError("step IDs must be unique")
        if len(set(self.credential_aliases)) != len(self.credential_aliases):
            raise ValueError("credential aliases must be unique")
        aliases = set(self.credential_aliases)
        for alias in aliases:
            if re.fullmatch(IDENTIFIER_PATTERN, alias) is None:
                raise ValueError("credential alias is invalid")
        for key, value in self.labels.items():
            if re.fullmatch(IDENTIFIER_PATTERN, key) is None or not 1 <= len(value) <= 120:
                raise ValueError("label is invalid")
            if SENSITIVE_KEY.search(key):
                raise ValueError("secret-like label keys are forbidden")
        known_steps = set(step_ids)
        steps_by_id = {step.id: step for step in self.steps}
        edge_keys: set[tuple[str, str, str]] = set()
        adjacency = {step_id: set[str]() for step_id in step_ids}
        indegree = dict.fromkeys(step_ids, 0)
        for edge in self.edges:
            if edge.from_step not in known_steps or edge.to_step not in known_steps:
                raise ValueError("edge references an unknown step")
            if edge.from_step == edge.to_step:
                raise ValueError("self-loop is not allowed")
            source = steps_by_id[edge.from_step]
            if isinstance(source, ActionStep) and edge.outcome not in {
                "SUCCESS",
                "FAILURE",
                "ALWAYS",
            }:
                raise ValueError("action edges require SUCCESS, FAILURE, or ALWAYS")
            if isinstance(source, ConditionStep) and edge.outcome not in {
                "TRUE",
                "FALSE",
            }:
                raise ValueError("condition edges require TRUE or FALSE")
            edge_key = (edge.from_step, edge.to_step, edge.outcome)
            if edge_key in edge_keys:
                raise ValueError("duplicate edge is not allowed")
            edge_keys.add(edge_key)
            if edge.to_step not in adjacency[edge.from_step]:
                adjacency[edge.from_step].add(edge.to_step)
                indegree[edge.to_step] += 1
        ready = [step_id for step_id, degree in indegree.items() if degree == 0]
        visited = 0
        while ready:
            current = ready.pop()
            visited += 1
            for target in adjacency[current]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)
        if visited != len(step_ids):
            raise ValueError("playbook graph must be acyclic")
        for step in self.steps:
            if isinstance(step, ActionStep) and not set(step.credential_aliases) <= aliases:
                raise ValueError("step uses an undeclared credential alias")
            if isinstance(step, ConditionStep):
                _validate_expression(step.expression, known_steps, depth=1)
                for dependency in _expression_step_dependencies(step.expression):
                    if not _has_path(adjacency, dependency, step.id):
                        raise ValueError("condition output references require an upstream step")
        if len(canonical_playbook_bytes(self)) > 262_144:
            raise ValueError("canonical playbook exceeds 256 KiB")
        return self


def _reject_sensitive_keys(value: JsonValue) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if SENSITIVE_KEY.search(key):
                raise ValueError("secret-like parameter keys are forbidden")
            _reject_sensitive_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_sensitive_keys(nested)


def _validate_expression(
    expression: ConditionExpression, known_steps: set[str], *, depth: int
) -> None:
    if depth > 8:
        raise ValueError("condition expression depth exceeds 8")
    if expression.path is not None:
        match = STEP_OUTPUT_PATH.match(expression.path)
        if match is not None and match.group(1) not in known_steps:
            raise ValueError("condition references an unknown step")
    for operand in expression.operands:
        _validate_expression(operand, known_steps, depth=depth + 1)


def _expression_step_dependencies(expression: ConditionExpression) -> set[str]:
    dependencies: set[str] = set()
    if expression.path is not None:
        match = STEP_OUTPUT_PATH.match(expression.path)
        if match is not None:
            dependencies.add(match.group(1))
    for operand in expression.operands:
        dependencies.update(_expression_step_dependencies(operand))
    return dependencies


def _has_path(adjacency: dict[str, set[str]], source: str, target: str) -> bool:
    pending = [source]
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current == target:
            return current != source
        if current in visited:
            continue
        visited.add(current)
        pending.extend(adjacency[current] - visited)
    return False


def canonical_playbook_bytes(playbook: PortablePlaybookV1) -> bytes:
    return json.dumps(
        playbook.model_dump(mode="json", exclude_none=True),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def portable_playbook_sha256(playbook: PortablePlaybookV1) -> str:
    return hashlib.sha256(canonical_playbook_bytes(playbook)).hexdigest()
