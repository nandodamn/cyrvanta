# Production Readiness Increment 41 — Human approval rationale

Date: 2026-08-13

## Objective

Ensure approval and rejection records contain the deciding analyst's actual rationale rather than
text synthesized by the frontend.

## Finding and implementation

The incident response UI previously sent a fixed English reason for every approval or rejection.
Although the backend persisted that field, the audit trail did not capture the analyst's own
judgment.

Both approval surfaces now require a bilingual, bounded rationale field. The action remains
disabled until non-whitespace content is present, the API sends the normalized operator text, and
the backend independently strips and rejects empty content before persisting the append-only
decision. Successful submission clears only that approval request's local rationale.

The UI also labels four-eyes completion only when the policy actually required at least two
approvals; a completed single-approval request is no longer presented as dual control.

## Security, tenancy, and audit

Existing authenticated tenant context, permission checks, requester/approver separation,
fingerprint verification, distinct-actor quorum, and audit/event persistence remain unchanged.
No tenant identifier or secret is accepted from the client.

## Verification status

Backend unit coverage was added for trimming and whitespace-only rejection. A frontend contract
test asserts the human input path and removal of synthesized reasons. Per operator instruction,
Codex did not execute tests, builds, services, Docker, probes, migrations, playbooks, or external
connections. Targeted Ruff static analysis passed. Frontend static checking was attempted before
the final minimal reapplication and exposed pre-existing unrelated type/test-fixture errors; no
test or build was executed.

## Rollback

Rollback is the implementation commit for this increment. It would restore misleading approval
audit content and is not recommended.
