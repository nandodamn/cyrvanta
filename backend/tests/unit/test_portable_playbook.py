import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import ValidationError

from cyrvanta.modules.playbooks.application.portable import (
    PortablePlaybookV1,
    portable_playbook_sha256,
)

ROOT = Path(__file__).parents[3]
ENGINE_ROOT = ROOT / "infrastructure" / "playbook_engine"


def load_exporter() -> ModuleType:
    path = ENGINE_ROOT / "scripts" / "export_schema.py"
    spec = importlib.util.spec_from_file_location("cyrvanta_playbook_schema", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load playbook schema exporter")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_fixture(name: str) -> dict[str, object]:
    value = json.loads((ENGINE_ROOT / "fixtures" / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("Fixture root must be an object")
    return value


def test_portable_playbook_fixture_is_strict_and_deterministic() -> None:
    payload = load_fixture("simulated-notification.json")
    first = PortablePlaybookV1.model_validate(payload)
    second = PortablePlaybookV1.model_validate(json.loads(json.dumps(payload)))

    assert portable_playbook_sha256(first) == portable_playbook_sha256(second)
    assert len(portable_playbook_sha256(first)) == 64


def test_portable_playbook_rejects_arbitrary_code() -> None:
    with pytest.raises(ValidationError):
        PortablePlaybookV1.model_validate(load_fixture("invalid-arbitrary-code.json"))


@pytest.mark.parametrize(
    "mutation",
    [
        {"parameters": {"api_key": "forbidden"}},
        {"credential_aliases": ["undeclared-alias"]},
    ],
)
def test_action_rejects_secret_material_and_undeclared_aliases(
    mutation: dict[str, object],
) -> None:
    payload = load_fixture("simulated-notification.json")
    step = payload["steps"][0]  # type: ignore[index]
    if not isinstance(step, dict):
        raise TypeError("Fixture action must be an object")
    step.update(mutation)

    with pytest.raises(ValidationError):
        PortablePlaybookV1.model_validate(payload)


def test_portable_playbook_rejects_cycles() -> None:
    payload = load_fixture("simulated-notification.json")
    edges = payload["edges"]
    if not isinstance(edges, list):
        raise TypeError("Fixture edges must be a list")
    edges.append({"from_step": "delivered", "to_step": "notify", "outcome": "TRUE"})

    with pytest.raises(ValidationError, match="acyclic"):
        PortablePlaybookV1.model_validate(payload)


@pytest.mark.parametrize(
    ("step_index", "outcome", "message"),
    [
        (0, "TRUE", "action edges require"),
        (1, "SUCCESS", "condition edges require"),
    ],
)
def test_edge_outcome_must_match_source_step_type(
    step_index: int, outcome: str, message: str
) -> None:
    payload = load_fixture("simulated-notification.json")
    steps = payload["steps"]
    if not isinstance(steps, list):
        raise TypeError("Fixture steps must be a list")
    source = steps[step_index]
    if not isinstance(source, dict):
        raise TypeError("Fixture step must be an object")
    payload["edges"] = [
        {
            "from_step": source["id"],
            "to_step": "notify" if step_index else "delivered",
            "outcome": outcome,
        }
    ]

    with pytest.raises(ValidationError, match=message):
        PortablePlaybookV1.model_validate(payload)


def test_condition_cannot_read_output_from_non_upstream_step() -> None:
    payload = load_fixture("simulated-notification.json")
    payload["edges"] = []

    with pytest.raises(ValidationError, match="upstream step"):
        PortablePlaybookV1.model_validate(payload)


def test_labels_reject_secret_like_keys() -> None:
    payload = load_fixture("simulated-notification.json")
    payload["labels"] = {"api_key": "must-not-be-stored"}

    with pytest.raises(ValidationError, match="secret-like"):
        PortablePlaybookV1.model_validate(payload)


def test_published_schema_matches_exporter() -> None:
    exporter = load_exporter()
    published = json.loads(
        (ENGINE_ROOT / "schemas" / "playbook-v1.schema.json").read_text(encoding="utf-8")
    )

    assert published == exporter.build_schema()
    assert published["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert published["$id"] == "urn:cyrvanta:playbook:1.0"
