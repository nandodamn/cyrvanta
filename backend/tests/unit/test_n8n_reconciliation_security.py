import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[3]


def load_reconciler() -> ModuleType:
    path = ROOT / "infrastructure" / "n8n" / "scripts" / "reconcile.py"
    spec = importlib.util.spec_from_file_location("cyrvanta_n8n_reconcile", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load the n8n reconciler")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reconciler_requires_explicit_host_api_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_reconciler()
    monkeypatch.delenv("N8N_API_URL", raising=False)
    monkeypatch.delenv("N8N_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="N8N_API_URL"):
        module.reconcile(apply=False)


def test_reconciler_requires_external_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_reconciler()
    monkeypatch.setenv("N8N_API_URL", "http://localhost:5678")
    monkeypatch.delenv("N8N_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="N8N_API_KEY"):
        module.reconcile(apply=False)


def test_installed_workflow_comparison_ignores_api_only_metadata() -> None:
    module = load_reconciler()
    source = {
        "id": "portable-id",
        "name": "Portable workflow",
        "active": False,
        "nodes": [],
        "connections": {},
    }
    observed = {
        **source,
        "active": True,
        "activeVersion": {},
        "activeVersionId": "runtime-active-version",
        "createdAt": "2026-08-01T00:00:00.000Z",
        "description": None,
        "isArchived": False,
        "meta": {},
        "shared": [],
        "triggerCount": 0,
        "updatedAt": "2026-08-01T00:00:01.000Z",
        "versionCounter": 4,
        "versionId": "runtime-version",
    }
    comparable = module.comparable_installed_workflow(source, observed)
    changed = module.comparable_installed_workflow(source, {**observed, "name": "Changed"})

    assert module.canonical_workflow(comparable) == module.canonical_workflow(source)
    assert module.canonical_workflow(changed) != module.canonical_workflow(source)
