# Production Readiness Increment 26 — Reproducible backend dependency chain

Date: 2026-08-11

## Objective

Prevent backend builds from silently selecting new runtime packages or trusting unreviewed
artifacts.

## Implementation

- Python 3.12.10 slim is pinned to its observed SHA-256 image digest.
- Hatchling is pinned to version 1.32.0 in the PEP 517 build contract.
- `requirements.lock` contains the complete Linux runtime closure with exact versions and
  accepted SHA-256 distribution hashes.
- Docker installs the lock with `--require-hashes` and installs Cyrvanta with `--no-deps`.
- A regression test protects the digest, hashed-install flags, non-root runtime user, pinned
  build backend, secure cryptography version, and lock structure.
- `backend/DEPENDENCIES.md` defines the reviewed update procedure using pip-tools 7.6.0 and
  `--reuse-hashes`.

## Verification

```text
No-cache locked image build: passed
pip check: No broken requirements found
pip-audit: No known vulnerabilities found
Backend tests without PostgreSQL: 218 passed
PostgreSQL-backed test: 1 passed
Ruff: all checks passed
Mypy: no issues in 130 source files
```

Two consecutive `pip-compile --reuse-hashes` runs produced the identical lock SHA-256:

```text
1D3539DB5DF949CFD1425E3FBDF9151426349C0147A930EE0275F7A0307E6CDD
```

A from-scratch second resolution observed additional hashes published for an unchanged
SQLAlchemy version. Those hashes were not silently trusted. This demonstrates why the
committed lock and `--reuse-hashes` workflow are required.

The final result is 219 backend tests across the isolated runtime and PostgreSQL-backed run.

## Contract and security impact

No domain, database, API, event, permission, tenant, secret, or LIVE automation contract
changed. The build remains network-dependent when fetching already hashed distributions;
an internal wheel mirror is a later availability hardening option.

## Rollback

Rollback is code-only, but returning to unconstrained installation is not recommended. A lock
update should instead be reviewed, audited, tested, and committed as a new immutable change.
