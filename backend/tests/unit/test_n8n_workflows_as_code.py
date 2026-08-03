import json
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).parents[3] / "infrastructure" / "n8n"


def test_manifest_registers_five_inactive_synthetic_artifacts() -> None:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    entries = manifest["workflows"]
    assert {item["code"] for item in entries} == {
        "notify-critical-incident",
        "create-security-ticket",
        "request-dual-approval",
        "simulate-user-block",
        "incident-report-email",
    }
    assert all(item["classification"] == "synthetic" for item in entries)
    for entry in entries:
        workflow = json.loads((ROOT / entry["file"]).read_text(encoding="utf-8"))[0]
        assert workflow["active"] is False
        for node in workflow["nodes"]:
            if node["type"] == "n8n-nodes-base.webhook":
                UUID(str(node["webhookId"]))


def test_synthetic_demo_claims_before_reporting_result() -> None:
    workflow = json.loads(
        (ROOT / "workflows" / "simulate-user-block.json").read_text(encoding="utf-8")
    )[0]
    connections = workflow["connections"]
    assert connections["Authorized Dispatch"]["main"][0][0]["node"] == "Claim Before Effect"
    assert connections["Claim Before Effect"]["main"][0][0]["node"] == ("Report Synthetic Result")
    node_types = {node["type"] for node in workflow["nodes"]}
    assert "n8n-nodes-base.code" not in node_types
    assert "n8n-nodes-base.executeCommand" not in node_types
