# Production Readiness Increment 25 — Cryptography vulnerability remediation

Date: 2026-08-11

## Objective

Remove known vulnerabilities from the backend image before producing a dependency lock.

## Finding

`pip-audit` against the deployed image reported nine vulnerability records affecting
`cryptography 45.0.7`. The existing direct dependency range (`>=43,<46`) prevented pip from
selecting the corrected releases reported by the advisory service.

## Remediation

The supported range is now `cryptography>=50,<51`. A candidate image resolved
`cryptography 50.0.0`. Cyrvanta uses stable cryptographic primitives exposed by the package;
no application API, stored ciphertext format, domain contract, tenant behavior, or migration
changed.

## Verification

```text
Candidate backend image build: passed
pip-audit before remediation: 9 known vulnerability records in cryptography 45.0.7
pip-audit after remediation: No known vulnerabilities found
Backend tests without PostgreSQL: 217 passed
PostgreSQL-backed alert triage test: 1 passed
```

The 217-test run used the complete repository mounted read-only into the candidate image.
The PostgreSQL test used a disposable runner derived from that same image on the isolated
Compose network. Read-only pytest-cache warnings do not affect test execution.

The local Cyrvanta package is intentionally skipped by `pip-audit` because it is private and
not published on PyPI; all installed third-party packages were audited.

## Security and rollback

The vulnerable deployed image is not considered suitable for production. Deployment of this
change requires rebuilding backend, worker, and scheduler and repeating health probes.
Rollback to the old cryptography range is not recommended; a compatibility failure should be
handled by selecting another audited corrected release instead.

Deterministic runtime dependency constraints remain the next task. The vulnerable dependency
set will not be used as the basis for that lock.
