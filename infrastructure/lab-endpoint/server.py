"""Lab-only HTTP endpoint for playbook actions that call an external system.

Stands in for the third-party systems a tenant would configure -- a threat
intelligence source and a ticketing platform -- so an end-to-end run performs a
real, verifiable HTTPS-shaped egress inside the lab network instead of
depending on an internet service.

What is real: the POST, its headers, the idempotency key, the response, and the
audit trail Cyrvanta records for it. What is NOT real: the reputation verdicts
and the ticket ids, which are derived from the request itself. Never present a
verdict from this service as a genuine assessment of an indicator.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG = logging.getLogger("lab-endpoint")

# Cyrvanta only accepts these four, and rejects the response otherwise.
_VERDICTS = ("benign", "suspicious", "malicious", "unknown")
_MAX_BODY_BYTES = 256 * 1024


def _verdict_for(body: bytes) -> tuple[str, int]:
    """Pick a stable verdict from the request so replays stay consistent.

    A random verdict would make the same incident look different on every run,
    which reads as a flaky integration rather than a deterministic one.
    """
    digest = hashlib.sha256(body).digest()
    verdict = _VERDICTS[digest[0] % len(_VERDICTS)]
    return verdict, digest[1] % 101


class Handler(BaseHTTPRequestHandler):
    server_version = "CyrvantaLabEndpoint/1.0"

    def _respond(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Request-Id", payload.get("request_id", "lab-endpoint"))  # type: ignore[arg-type]
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path == "/health":
            self._respond(200, {"status": "ok", "request_id": "health"})
            return
        self._respond(404, {"error": "not_found", "request_id": "none"})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._respond(400, {"error": "bad_length", "request_id": "none"})
            return
        if length > _MAX_BODY_BYTES:
            self._respond(413, {"error": "too_large", "request_id": "none"})
            return
        body = self.rfile.read(length) if length else b""
        # The idempotency key is what makes a replay identifiable, so it is
        # echoed back rather than invented here.
        idempotency = self.headers.get("Idempotency-Key", "")
        request_id = hashlib.sha256(f"{self.path}:{idempotency}".encode()).hexdigest()[:16]
        LOG.info(
            "%s len=%d idempotency=%s tenant=%s",
            self.path,
            length,
            idempotency[:16],
            self.headers.get("X-Cyrvanta-Tenant", "-"),
        )

        if self.path.startswith("/threat-intel"):
            verdict, score = _verdict_for(body)
            self._respond(
                200,
                {
                    # Exactly the contract Cyrvanta validates; anything else is
                    # rejected instead of being filed as incident context.
                    "verdict": verdict,
                    "score": score,
                    "source": "Cyrvanta Lab Endpoint (no es una fuente real)",
                    "request_id": request_id,
                },
            )
            return
        if self.path.startswith("/tickets"):
            self._respond(
                201,
                {"id": f"LAB-{request_id[:8].upper()}", "status": "open", "request_id": request_id},
            )
            return
        # Anything else still answers, so a webhook step has somewhere to point.
        self._respond(202, {"accepted": True, "request_id": request_id})

    def log_message(self, fmt: str, *args: object) -> None:
        LOG.info(fmt, *args)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    port = int(os.environ.get("LAB_ENDPOINT_PORT", "8081"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    LOG.info("lab endpoint listening on %d", port)
    server.serve_forever()


if __name__ == "__main__":
    main()
