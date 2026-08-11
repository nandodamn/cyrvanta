import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_backend_runtime_build_is_pinned_and_hash_verified() -> None:
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    pyproject = tomllib.loads((ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8"))
    lock = (ROOT / "backend" / "requirements.lock").read_text(encoding="utf-8")

    assert re.search(
        r"^FROM python:3\.12\.10-slim@sha256:[0-9a-f]{64} AS runtime$", dockerfile, re.M
    )
    assert "--require-hashes -r requirements.lock" in dockerfile
    assert "pip install --no-cache-dir --no-deps ." in dockerfile
    assert re.search(r"^USER cyrvanta$", dockerfile, re.M)
    assert pyproject["build-system"]["requires"] == ["hatchling==1.32.0"]
    assert "cryptography==50.0.0" in lock
    assert "--index-url" not in lock
    assert lock.count("--hash=sha256:") >= 40

    requirement_lines = [
        line
        for line in lock.splitlines()
        if line and not line[0].isspace() and not line.startswith("#")
    ]
    assert requirement_lines
    assert all(re.match(r"^[a-z0-9][a-z0-9_.-]*==[^ ]+ \\$", line) for line in requirement_lines)
