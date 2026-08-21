"""What a managed n8n artifact must be, whatever it turns out to be.

These used to assert the five synthetic demo workflows by name. Those are gone
-- four were webhooks that answered "fail closed" and one reported a simulated
success -- so the manifest ships empty and n8n is an extension point with
nothing plugged into it.

A test naming specific artifacts would now pass by describing nothing. These
guard the properties instead, so they hold today with an empty manifest and
keep holding the first time somebody adds a real workflow.
"""

import json
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).parents[3] / "infrastructure" / "n8n"
MANIFEST = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
ENTRIES = MANIFEST["workflows"]


def test_the_manifest_is_readable_and_declares_its_schema() -> None:
    assert MANIFEST["schema_version"] == 1
    assert MANIFEST["managed_by"] == "cyrvanta"
    assert isinstance(ENTRIES, list)


def test_every_declared_workflow_has_an_artifact_on_disk() -> None:
    """A manifest entry whose file is missing would reconcile to nothing while
    reporting a managed workflow.
    """
    for entry in ENTRIES:
        assert (ROOT / entry["file"]).is_file(), entry["code"]


def test_every_artifact_ships_inactive() -> None:
    """Activation is an operational decision taken against a reviewed digest.
    An artifact that arrives active has skipped it.
    """
    for entry in ENTRIES:
        workflow = json.loads((ROOT / entry["file"]).read_text(encoding="utf-8"))[0]
        assert workflow["active"] is False, entry["code"]


def test_every_webhook_carries_a_real_identifier() -> None:
    """n8n routes by webhook id. A hand-written or duplicated one silently
    collides with another workflow's endpoint.
    """
    for entry in ENTRIES:
        workflow = json.loads((ROOT / entry["file"]).read_text(encoding="utf-8"))[0]
        for node in workflow["nodes"]:
            if node["type"] == "n8n-nodes-base.webhook":
                UUID(str(node["webhookId"]))


def test_no_artifact_may_run_arbitrary_code() -> None:
    """The point of managing these as code is that a reader can tell what a
    workflow does. A `code` or `executeCommand` node makes the artifact a
    program the digest happens to cover rather than a procedure anyone reviewed.
    """
    for entry in ENTRIES:
        workflow = json.loads((ROOT / entry["file"]).read_text(encoding="utf-8"))[0]
        node_types = {node["type"] for node in workflow["nodes"]}
        assert "n8n-nodes-base.code" not in node_types, entry["code"]
        assert "n8n-nodes-base.executeCommand" not in node_types, entry["code"]


def test_no_orphan_artifacts_outside_the_manifest() -> None:
    """The legacy `cyrvanta-demo-response.json` sat here for months outside the
    manifest, imported by nothing and retired by nobody. An artifact the
    manifest does not declare is one no digest covers.
    """
    declared = {ROOT / entry["file"] for entry in ENTRIES}
    on_disk = set((ROOT / "workflows").glob("*.json")) if (ROOT / "workflows").is_dir() else set()
    assert on_disk - declared == set()
    assert list(ROOT.glob("*.json")) == [ROOT / "manifest.json"]
