"""Lab-only HTTP endpoint for playbook actions that call an external system.

Stands in for the third-party systems a tenant would configure -- a threat
intelligence source and a ticketing platform -- so an end-to-end run performs a
real, verifiable HTTPS-shaped egress inside the lab network instead of
depending on an internet service.

What is real: the POST, its headers, the idempotency key, the response, and the
audit trail Cyrvanta records for it. What is NOT real: the reputation verdicts
and the ticket ids. Never present a verdict from this service as a genuine
assessment of an indicator.

Verdicts come from the table below and nowhere else: every indicator in it is
from a range reserved for documentation (RFC 5737, RFC 2606), so none of them
can collide with a real host, and the reason a demo produced a given verdict is
readable here rather than hidden in a hash.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG = logging.getLogger("lab-endpoint")

# Cyrvanta only accepts these four verdicts and rejects the response otherwise.
#
# indicator -> (verdict, score, note). Documentation ranges only.
_INDICATORS: dict[str, tuple[str, int, str]] = {
    "192.0.2.10": ("malicious", 95, "Servidor de mando y control de laboratorio"),
    "192.0.2.20": ("malicious", 88, "Distribucion de malware de laboratorio"),
    "198.51.100.10": ("suspicious", 64, "Escaneo saliente inusual de laboratorio"),
    "198.51.100.20": ("suspicious", 51, "Reputacion mixta de laboratorio"),
    "203.0.113.10": ("benign", 3, "Servicio corporativo conocido de laboratorio"),
    "malware.example": ("malicious", 92, "Dominio de descarga de laboratorio"),
    "phishing.example": ("suspicious", 73, "Dominio de phishing de laboratorio"),
    "corporativo.example": ("benign", 2, "Dominio propio de laboratorio"),
}

# Loose on purpose: the indicator arrives inside incident text, not in a field
# of its own, so it has to be recognised wherever it was written.
_CANDIDATE = re.compile(
    r"\b(?:\d{1,3}(?:\.\d{1,3}){3}|[a-z0-9][a-z0-9.-]*\.example)\b",
    re.IGNORECASE,
)
_MAX_BODY_BYTES = 256 * 1024


def _lookup(body: bytes) -> tuple[str, int, str | None, str | None]:
    """Return the verdict for the first known indicator found in the request.

    An indicator that is not in the table is reported as unknown rather than
    guessed: inventing a verdict for it is what makes a demo misleading.
    """
    try:
        text = body.decode("utf-8", errors="replace")
    except Exception:  # pragma: no cover - decode never raises with replace
        return "unknown", 0, None, None
    for candidate in _CANDIDATE.findall(text):
        entry = _INDICATORS.get(candidate.lower())
        if entry is not None:
            verdict, score, note = entry
            return verdict, score, candidate.lower(), note
    return "unknown", 0, None, None


class Handler(BaseHTTPRequestHandler):
    server_version = "CyrvantaLabEndpoint/1.0"

    def _respond(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Request-Id", str(payload.get("request_id", "lab-endpoint")))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path == "/health":
            self._respond(200, {"status": "ok", "request_id": "health"})
            return
        if self.path.startswith("/threat-intel/indicators"):
            # The table is readable at runtime so a demo can show what the
            # source knows before anyone asks why a verdict came out that way.
            self._respond(
                200,
                {
                    "disclaimer": "Indicadores ficticios de laboratorio (RFC 5737 / RFC 2606).",
                    "indicators": {
                        key: {"verdict": v, "score": s, "note": n}
                        for key, (v, s, n) in sorted(_INDICATORS.items())
                    },
                    "request_id": "indicators",
                },
            )
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
            verdict, score, matched, note = _lookup(body)
            LOG.info("threat-intel matched=%s verdict=%s", matched or "-", verdict)
            self._respond(
                200,
                {
                    # Exactly the contract Cyrvanta validates; anything else is
                    # rejected instead of being filed as incident context.
                    "verdict": verdict,
                    "score": score,
                    "source": "Cyrvanta Lab Endpoint (no es una fuente real)",
                    "matched_indicator": matched,
                    "note": note,
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
