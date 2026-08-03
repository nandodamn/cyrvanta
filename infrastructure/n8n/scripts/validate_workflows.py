import hashlib
import json
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_FIELDS = {
    "active",
    "createdAt",
    "id",
    "shared",
    "tags",
    "updatedAt",
    "versionId",
}
FORBIDDEN = {
    "n8n-nodes-base.code",
    "n8n-nodes-base.executeCommand",
    "n8n-nodes-base.function",
    "n8n-nodes-base.functionItem",
    "n8n-nodes-base.readWriteFile",
    "n8n-nodes-base.ssh",
}


def canonical_workflow(workflow: dict[str, object]) -> bytes:
    material = {
        key: value for key, value in workflow.items() if key not in RUNTIME_FIELDS
    }
    return json.dumps(
        material, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()


def main() -> None:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    codes: set[str] = set()
    for entry in manifest["workflows"]:
        code = entry["code"]
        if code in codes:
            raise ValueError(f"duplicate workflow code: {code}")
        codes.add(code)
        path = ROOT / entry["file"]
        for schema_key in ("input_schema", "result_schema"):
            schema = json.loads((ROOT / entry[schema_key]).read_text(encoding="utf-8"))
            if schema.get("type") != "object":
                raise ValueError(f"{code}: {schema_key} must define an object")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list) or len(payload) != 1:
            raise ValueError(f"{path.name}: export must contain exactly one workflow")
        workflow = payload[0]
        if workflow.get("active") is not False:
            raise ValueError(f"{path.name}: Git artifact must be inactive")
        node_types = {node.get("type") for node in workflow.get("nodes", [])}
        dangerous = sorted(node_types & FORBIDDEN)
        if dangerous:
            raise ValueError(f"{path.name}: forbidden nodes: {dangerous}")
        for node in workflow.get("nodes", []):
            if node.get("type") != "n8n-nodes-base.webhook":
                continue
            try:
                UUID(str(node["webhookId"]))
            except (KeyError, ValueError) as exc:
                raise ValueError(
                    f"{path.name}: webhook nodes require a stable UUID webhookId"
                ) from exc
        names = {node.get("name") for node in workflow.get("nodes", [])}
        if None in names or len(names) != len(workflow.get("nodes", [])):
            raise ValueError(f"{path.name}: node names must be present and unique")
        connections = workflow.get("connections")
        if not isinstance(connections, dict):
            raise TypeError(f"{path.name}: connections must be an object")
        for source, groups in connections.items():
            if source not in names:
                raise ValueError(f"{path.name}: unknown connection source {source}")
            for branch in groups.get("main", []):
                for target in branch:
                    if target.get("node") not in names:
                        raise ValueError(
                            f"{path.name}: unknown connection target {target.get('node')}"
                        )
        if (
            code == "simulate-user-block"
            and not {
                "Claim Before Effect",
                "Report Synthetic Result",
            }
            <= names
        ):
            raise ValueError(f"{path.name}: safe claim/callback chain is missing")
        digest = hashlib.sha256(canonical_workflow(workflow)).hexdigest()
        if entry.get("sha256") != digest:
            raise ValueError(f"{path.name}: manifest digest mismatch")
        print(f"{code} {digest}")


if __name__ == "__main__":
    main()
