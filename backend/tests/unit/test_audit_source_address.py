"""Where an audited action came from.

An audit that says who did what and not from where answers half the question,
and the missing half is the one that separates a supervisor approving a
containment from their desk from the same credentials approving it from an
address nobody recognises.

The address is taken from the connection rather than from a header the caller
controls, and it reaches the record through a context variable rather than a
parameter threaded through every audit call site -- which is why these check
the wiring rather than a single function's return value.
"""

import re
from pathlib import Path

from cyrvanta.modules.identity.infrastructure.models import AuditEventModel
from cyrvanta.shared.request_context import current_source_address, set_source_address

COMPOSE = Path("../docker-compose.yml").read_text(encoding="utf-8")
MIDDLEWARE = Path("src/cyrvanta/shared/http.py").read_text(encoding="utf-8")


def test_an_audit_row_takes_the_address_of_the_request_it_serves() -> None:
    """Filled by the column default, so no writer has to pass it and none can
    forget to.
    """
    set_source_address("203.0.113.9")
    try:
        assert AuditEventModel.__table__.c.source_address.default.arg(None) == "203.0.113.9"
    finally:
        set_source_address(None)


def test_background_work_records_no_address_rather_than_a_wrong_one() -> None:
    """A scheduler expiring a memory is not acting from anywhere. Inheriting
    the address of whoever last made a request would put a false fact in the
    one table that exists to be trusted.
    """
    set_source_address(None)
    assert current_source_address() is None
    assert AuditEventModel.__table__.c.source_address.default.arg(None) is None


def test_the_column_accepts_an_absent_address() -> None:
    """Rows written before this existed cannot say where they came from, and
    must not be forced to claim something.
    """
    assert AuditEventModel.__table__.c.source_address.nullable


def test_the_column_holds_the_longest_address_a_client_can_have() -> None:
    """45 characters is an IPv6 address with an IPv4-mapped suffix. A shorter
    column would truncate one, and a truncated address is worse than none.
    """
    assert AuditEventModel.__table__.c.source_address.type.length == 45


def test_the_address_comes_from_the_connection_not_from_a_header() -> None:
    """X-Forwarded-For is set by whoever is calling. Reading it directly would
    let any client write its own line in the audit trail.
    """
    collapsed = re.sub(r"\s+", " ", MIDDLEWARE)
    assert "set_source_address(request.client.host if request.client else None)" in collapsed
    # The header may be named in a comment explaining why it is not trusted;
    # what must not appear is a read of it.
    assert not re.search(r"headers[\.\[]\s*(get\()?\s*[\"']x-forwarded", collapsed, re.IGNORECASE)


def test_the_server_is_told_to_trust_the_proxy_it_sits_behind() -> None:
    """Without --proxy-headers the connection address is the reverse proxy's,
    so every entry would name the same container.
    """
    assert "--proxy-headers" in COMPOSE


def test_the_proxy_forwards_the_header_the_server_reads() -> None:
    """The two halves have to match, and once did not.

    nginx sent X-Real-IP and X-Forwarded-Proto; uvicorn's --proxy-headers reads
    X-Forwarded-For. With the flag set and the header missing, every entry
    recorded the proxy's own container address -- which is worse than recording
    none, because it looks like an answer.
    """
    nginx = Path("../infrastructure/nginx/default.conf").read_text(encoding="utf-8")
    assert "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;" in nginx


def test_the_backend_publishes_no_port() -> None:
    """--forwarded-allow-ips='*' is only safe while the proxy is the sole
    source of those headers. Publishing this service would turn that setting
    into a way to forge an audit trail, so the two belong in one test.
    """
    backend = COMPOSE.split("  backend:")[1].split("\n  worker:")[0]
    assert "--forwarded-allow-ips" in backend
    assert "ports:" not in backend
