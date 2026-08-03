from __future__ import annotations

import hashlib
import json

from cyrvanta.modules.playbooks.application.engine_ports import (
    ActionConnectorPort,
    ActionDescriptor,
    ActionResult,
    CredentialHandle,
    EngineContext,
    ProbeResult,
    ValidationResult,
)

SIMULATED_ACTIONS = (
    "notification.send",
    "ticket.create",
    "incident.report.generate",
    "webhook.invoke_allowlisted",
    "endpoint.isolate_simulated",
)


class ActionUnavailableError(LookupError):
    pass


class SimulatedActionConnector:
    def __init__(self, code: str) -> None:
        if code not in SIMULATED_ACTIONS:
            raise ValueError("action is not allowlisted")
        self._code = code

    def describe(self) -> ActionDescriptor:
        return ActionDescriptor(
            code=self._code,
            version="1.0.0",
            modes=("SIMULATED",),
            impact="LOW",
            timeout_seconds=30,
            retry_safe=True,
            cancellable=True,
            egress="NONE",
        )

    def validate_configuration(self, configuration: dict[str, object]) -> ValidationResult:
        if configuration:
            return ValidationResult(False, ("PLAYBOOK_ACTION_CONFIG_INVALID",))
        return ValidationResult(True)

    async def probe(self, context: EngineContext, configuration: dict[str, object]) -> ProbeResult:
        del context
        validation = self.validate_configuration(configuration)
        return ProbeResult(
            healthy=validation.valid,
            error_code=None if validation.valid else validation.error_codes[0],
        )

    async def execute(
        self,
        context: EngineContext,
        action_input: dict[str, object],
        idempotency_key: str,
        credential_handle: CredentialHandle | None,
    ) -> ActionResult:
        del context, credential_handle
        material = json.dumps(
            {"action": self._code, "input": action_input, "key": idempotency_key},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        output: dict[str, object] = {
            "simulated": True,
            "effect": "none",
            "action_code": self._code,
            "receipt": hashlib.sha256(material).hexdigest()[:24],
        }
        if self._code == "notification.send":
            output["status"] = "DELIVERED"
        elif self._code == "ticket.create":
            output["status"] = "CREATED"
        elif self._code == "incident.report.generate":
            output["status"] = "GENERATED"
        elif self._code == "webhook.invoke_allowlisted":
            output["status"] = "ACCEPTED"
        else:
            output["status"] = "ISOLATION_SIMULATED"
        return ActionResult(
            succeeded=True,
            output=output,
            safe_detail="Simulated action completed without external effects",
        )


class ActionRegistry:
    def __init__(self) -> None:
        self._connectors: dict[tuple[str, str], ActionConnectorPort] = {
            (code, "1.0.0"): SimulatedActionConnector(code) for code in SIMULATED_ACTIONS
        }

    def get(self, code: str, version: str) -> ActionConnectorPort:
        try:
            return self._connectors[(code, version)]
        except KeyError as exc:
            raise ActionUnavailableError("PLAYBOOK_ACTION_UNAVAILABLE") from exc

    def descriptors(self) -> tuple[ActionDescriptor, ...]:
        return tuple(
            connector.describe()
            for _, connector in sorted(self._connectors.items(), key=lambda item: item[0])
        )
