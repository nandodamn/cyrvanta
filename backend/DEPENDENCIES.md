# Backend dependency lock

`requirements.lock` is the reviewed runtime dependency closure for the Linux backend image.
Every package is pinned and every accepted distribution has a SHA-256 hash. The Docker build
installs this file with `--require-hashes`, then installs Cyrvanta itself with `--no-deps` so
pip cannot resolve a second dependency graph.

Generate or deliberately update the lock from the repository root with Docker and
`pip-tools==7.6.0`. Preserve reviewed hashes for unchanged versions:

```powershell
docker run --rm `
  -v "${PWD}/backend:/src" `
  -w /src `
  python:3.12.10-slim@sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db `
  /bin/sh -c "python -m pip install -q pip-tools==7.6.0 && python -m piptools compile --reuse-hashes --generate-hashes --resolver=backtracking --strip-extras --no-emit-index-url --output-file=requirements.lock pyproject.toml"
```

Review version and hash changes, build once with `--no-cache`, run `pip check`, run
`pip-audit`, and execute the complete backend suite before accepting an updated lock. Never
replace the committed lock with an unconstrained `pip freeze` output.
