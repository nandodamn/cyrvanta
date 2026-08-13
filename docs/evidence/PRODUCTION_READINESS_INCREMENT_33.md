# Production Readiness Increment 33 — Validated real egress targets

Date: 2026-08-13

## Objective

Apply the operator authorization for the real `notify-critical-incident`,
`create-security-ticket`, and `incident-report-email` playbooks without activating or
executing them automatically.

## Finding and implementation

The real SMTP and HTTP actions already depended on tenant-scoped, active, verified
connections and the publication, approval, LIVE, dispatch, and kill-switch gates. Their
configuration validation was nevertheless too permissive for production egress.

The implementation now:

- accepts connector-specific fields only and rejects credentials a connector will ignore;
- validates bounded typed timeouts, ports, TLS settings, credentials, and paired basic auth;
- rejects URL user information, query strings, fragments, invalid ports, ambiguous HTTP auth,
  and non-HTTPS non-loopback production origins;
- requires a single safe SMTP sender and recipient mailbox;
- rejects control characters in headers, hosts, URLs, and credentials;
- limits HTTP actions to a bounded relative POST path without traversal, query, fragment,
  external origin, or free method;
- uses the same supported HTTP API-key authentication during verification and execution.

No binding, connection, approval, or LIVE switch is activated by this change. No external
request or email is emitted by configuration or publication.

## Verification status

Unit tests were added for the destination, transport, typing, traversal, header-injection,
field allowlist, TLS, and authentication guards. Per operator instruction, Codex did not
execute tests, builds, probes, services, Docker, migrations, playbooks, or external
connections. Static diff validation and local source formatting were performed only.

## Contract and rollback

No endpoint, DTO, event, permission, database, or secret-storage contract changed. Existing
stored configurations containing ignored or ambiguous fields must be replaced and verified
before they can become ready. Rollback is the single implementation commit, but would restore
the permissive egress validation and is not recommended.
