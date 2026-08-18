from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
from sqlalchemy import delete, select, text

from cyrvanta.modules.claims.infrastructure.models import (
    ClaimEvidenceLinkModel,
    ClaimModel,
    ClaimPresentationModel,
)
from cyrvanta.modules.incident.infrastructure.models import IncidentModel
from cyrvanta.modules.integrations.application.connection_service import (
    StoredIntegrationCredential,
)
from cyrvanta.modules.playbooks.application.engine_ports import EngineContext
from cyrvanta.modules.playbooks.infrastructure.action_registry import ActionRegistry
from cyrvanta.shared.database import SessionFactory, tenant_session


async def _existing_tenant_id() -> UUID:
    async with SessionFactory() as session, session.begin():
        await session.execute(text("SELECT set_config('app.auth_lookup', 'true', true)"))
        return (await session.execute(text("SELECT id FROM tenants LIMIT 1"))).scalar()


def _context(tenant_id: UUID) -> EngineContext:
    return EngineContext(
        tenant_id=tenant_id, correlation_id=uuid4(), causation_id=None, deadline=datetime.now(UTC)
    )


def _credential() -> StoredIntegrationCredential:
    return StoredIntegrationCredential(
        reference="threat-intel-primary",
        values={"base_url": "https://ti.test", "api_key": "secret", "timeout_seconds": 5},
    )


_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _patch_httpx(monkeypatch, handler) -> None:
    # Always build on the real client: these tests repatch between payloads, and
    # wrapping the previous factory would pass transport twice.
    def factory(*args, **kwargs):
        kwargs.pop("verify", None)
        kwargs.pop("transport", None)
        return _REAL_ASYNC_CLIENT(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr("httpx.AsyncClient", factory)


def _responding(payload: object, status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload)

    return handler


@asynccontextmanager
async def _incident(tenant_id: UUID):
    incident_id = uuid4()
    async with tenant_session(tenant_id) as session:
        session.add(
            IncidentModel(
                id=incident_id,
                tenant_id=tenant_id,
                code=f"TI-{incident_id.hex[:8]}",
                title="Threat intel enrichment fixture",
                description="Created by test_threat_intel_enrichment.",
                status="new",
                severity="medium",
                priority=3,
                classification="test-fixture",
                version=1,
                detected_at=datetime.now(UTC),
            )
        )
    try:
        yield incident_id
    finally:
        async with tenant_session(tenant_id) as session:
            claim_ids = select(ClaimModel.id).where(
                ClaimModel.tenant_id == tenant_id,
                ClaimModel.incident_id == incident_id,
            )
            await session.execute(
                delete(ClaimEvidenceLinkModel).where(
                    ClaimEvidenceLinkModel.tenant_id == tenant_id,
                    ClaimEvidenceLinkModel.claim_id.in_(claim_ids),
                )
            )
            await session.execute(
                delete(ClaimPresentationModel).where(
                    ClaimPresentationModel.tenant_id == tenant_id,
                    ClaimPresentationModel.claim_id.in_(claim_ids),
                )
            )
            await session.execute(
                delete(ClaimModel).where(
                    ClaimModel.tenant_id == tenant_id, ClaimModel.incident_id == incident_id
                )
            )
            await session.execute(
                delete(IncidentModel).where(
                    IncidentModel.tenant_id == tenant_id, IncidentModel.id == incident_id
                )
            )


def _action_input(incident_id: UUID) -> dict[str, object]:
    return {
        "inputs": {
            "incident_id": str(incident_id),
            "incident_version": 1,
            "targets": ["1.2.3.4"],
            "parameters": {},
            "evidence_refs": [],
        },
        "parameters": {},
    }


async def test_lookup_files_the_verdict_as_incident_context(monkeypatch) -> None:
    tenant_id = await _existing_tenant_id()
    connector = ActionRegistry().get("threat_intel.lookup", "1.0.0")
    _patch_httpx(
        monkeypatch, _responding({"verdict": "malicious", "score": 90, "source": "OpenCTI"})
    )

    async with _incident(tenant_id) as incident_id:
        result = await connector.execute(
            _context(tenant_id),
            _action_input(incident_id),
            {"path": "/api/reputation"},
            f"ti-{incident_id}",
            _credential(),
        )

        assert result.succeeded is True
        assert result.output["verdict"] == "malicious"
        async with tenant_session(tenant_id) as session:
            claim = await session.scalar(
                select(ClaimModel).where(
                    ClaimModel.tenant_id == tenant_id, ClaimModel.incident_id == incident_id
                )
            )
        assert claim is not None
        # A report about what a third party said, attributed and non-authoritative.
        assert claim.origin_type == "SYSTEM"
        assert claim.claim_type == "DERIVED_FACT"
        assert claim.origin_code == "threat_intel.lookup"
        assert "malicious" in claim.statement
        assert "OpenCTI" in claim.statement
        assert claim.confidence is None


async def test_lookup_is_idempotent_for_the_same_response(monkeypatch) -> None:
    """Re-running the enrichment must not stack duplicate context on the incident."""
    tenant_id = await _existing_tenant_id()
    connector = ActionRegistry().get("threat_intel.lookup", "1.0.0")
    _patch_httpx(monkeypatch, _responding({"verdict": "benign"}))

    async with _incident(tenant_id) as incident_id:
        key = f"ti-repeat-{incident_id}"
        first = await connector.execute(
            _context(tenant_id), _action_input(incident_id), {"path": "/api/reputation"},
            key, _credential(),
        )
        second = await connector.execute(
            _context(tenant_id), _action_input(incident_id), {"path": "/api/reputation"},
            key, _credential(),
        )

        assert first.succeeded and second.succeeded
        assert first.output["claim_id"] == second.output["claim_id"]
        async with tenant_session(tenant_id) as session:
            claims = list(
                (
                    await session.scalars(
                        select(ClaimModel.id).where(
                            ClaimModel.tenant_id == tenant_id,
                            ClaimModel.incident_id == incident_id,
                        )
                    )
                ).all()
            )
        assert len(claims) == 1


async def test_unusable_responses_are_rejected_instead_of_filed(monkeypatch) -> None:
    """The response is untrusted input, not something to write down as given.

    A provider that answers with an unknown verdict, an out-of-range score or
    prose instead of an object must fail the action -- filing it would put
    unvalidated third-party content into the incident record.
    """
    tenant_id = await _existing_tenant_id()
    connector = ActionRegistry().get("threat_intel.lookup", "1.0.0")
    unusable: tuple[object, ...] = (
        {"verdict": "pwned"},
        {"verdict": 42},
        {},
        {"verdict": "benign", "score": 900},
        ["malicious"],
        "malicious",
    )

    async with _incident(tenant_id) as incident_id:
        for payload in unusable:
            _patch_httpx(monkeypatch, _responding(payload))
            result = await connector.execute(
                _context(tenant_id),
                _action_input(incident_id),
                {"path": "/api/reputation"},
                f"ti-bad-{incident_id}",
                _credential(),
            )
            assert result.succeeded is False, f"{payload!r} was accepted"
            assert result.error_code == "PLAYBOOK_ACTION_FAILED"

        async with tenant_session(tenant_id) as session:
            filed = await session.scalar(
                select(ClaimModel.id).where(
                    ClaimModel.tenant_id == tenant_id, ClaimModel.incident_id == incident_id
                )
            )
        assert filed is None


async def test_lookup_without_a_credential_never_calls_out(monkeypatch) -> None:
    tenant_id = await _existing_tenant_id()
    connector = ActionRegistry().get("threat_intel.lookup", "1.0.0")
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"verdict": "benign"})

    _patch_httpx(monkeypatch, handler)

    async with _incident(tenant_id) as incident_id:
        result = await connector.execute(
            _context(tenant_id),
            _action_input(incident_id),
            {"path": "/api/reputation"},
            f"ti-nocred-{incident_id}",
            None,
        )

    assert result.succeeded is False
    assert result.error_code == "PLAYBOOK_CREDENTIAL_UNAVAILABLE"
    assert calls == []


async def test_lookup_files_both_locales_without_a_human_translating(monkeypatch) -> None:
    """The claim must be readable in Spanish immediately, not after manual work.

    The statement is entirely deterministic (verdict, score, source), so
    requiring an analyst to open the claim and add a bilingual presentation by
    hand would leave every one of these claims in English until someone did
    that -- on a platform where bilingual is a first-class requirement.
    """
    tenant_id = await _existing_tenant_id()
    connector = ActionRegistry().get("threat_intel.lookup", "1.0.0")
    _patch_httpx(
        monkeypatch, _responding({"verdict": "malicious", "score": 90, "source": "OpenCTI"})
    )

    async with _incident(tenant_id) as incident_id:
        await connector.execute(
            _context(tenant_id),
            _action_input(incident_id),
            {"path": "/api/reputation"},
            f"ti-locale-{incident_id}",
            _credential(),
        )
        async with tenant_session(tenant_id) as session:
            claim = await session.scalar(
                select(ClaimModel).where(
                    ClaimModel.tenant_id == tenant_id, ClaimModel.incident_id == incident_id
                )
            )
            assert claim is not None
            presentations = list(
                (
                    await session.scalars(
                        select(ClaimPresentationModel).where(
                            ClaimPresentationModel.tenant_id == tenant_id,
                            ClaimPresentationModel.claim_id == claim.id,
                        )
                    )
                ).all()
            )
        by_locale = {item.locale: item.text for item in presentations}
        assert set(by_locale) == {"es", "en"}
        assert "malicioso" in by_locale["es"]
        assert "malicious" in by_locale["en"]
        # A rendering, not a person's account of what happened.
        assert all(item.origin_type == "RULE" for item in presentations)
