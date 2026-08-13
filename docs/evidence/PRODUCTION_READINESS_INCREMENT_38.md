# Production Readiness Increment 38 — Authoritative playbook governance

Date: 2026-08-13

## Objective

Prevent a client from lowering a released playbook's impact or approval quorum, and ensure a
tenant elevation to `FOUR_EYES` remains effective at proposal creation and immediately before
LIVE execution.

## Finding and implementation

The response client always requested `HUMAN_APPROVAL`, while the decision service accepted the
client-provided impact and mode as policy inputs. A tenant could configure `FOUR_EYES` in the
playbook library without that current governance becoming authoritative for the proposal.

Decision now obtains the exact tenant-scoped, approved, LIVE playbook version through an
application port. The playbook adapter resolves its persisted impact and maps
`AUTOMATIC | SINGLE | FOUR_EYES` to the decision modes. Missing, ambiguous, invalid, or
mismatched governance fails closed before persistence or authorization work. The frontend sends
the selected definition's actual mode instead of a fixed value.

Execution also revalidates the current definition mode, released version impact, stored proposal,
approval request, and actual approval count before queueing. A governance change after proposal
authorization therefore requires a new matching proposal and cannot reuse stale approval
material.

## Security and tenancy

Both definition and version are filtered by the authenticated tenant. No tenant identifier is
accepted from the request body, and the decision application depends on a port rather than the
playbook persistence implementation. No secret, external egress, schema migration, endpoint,
event, or permission contract changed.

## Verification status

Unit coverage was added for downgrade rejection, current four-eyes quorum, and governance changes
after authorization. Per operator instruction, Codex did not execute tests, builds, services,
Docker, probes, migrations, playbooks, or external connections. Targeted Ruff formatting and
static analysis passed, as did diff whitespace validation.

## Rollback

Rollback is the implementation commit for this increment. It would restore client-authoritative
approval inputs and is not recommended.
