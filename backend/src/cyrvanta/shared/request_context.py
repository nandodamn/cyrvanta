"""Where the request came from, available to code that never sees the request.

An audit record answers who did what. Without an address it cannot answer from
where, which is half of what an auditor asks and the half that distinguishes a
supervisor approving from their desk from the same credentials approving from
an address nobody recognises.

The alternative was threading a parameter through some fifty audit call sites
across every module. A context variable keeps the domain and infrastructure
layers free of the web framework -- nothing here imports FastAPI -- and gives
background work the honest answer: a scheduler expiring a memory has no client
address, and records none rather than inheriting somebody else's.
"""

from contextvars import ContextVar

_source_address: ContextVar[str | None] = ContextVar("cyrvanta_source_address", default=None)


def set_source_address(value: str | None) -> None:
    _source_address.set(value)


def current_source_address() -> str | None:
    """The caller's address, or None when nothing is serving a request."""
    return _source_address.get()
