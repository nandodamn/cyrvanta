import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {
    "n8n-nodes-base.code",
    "n8n-nodes-base.executeCommand",
    "n8n-nodes-base.function",
    "n8n-nodes-base.functionItem",
    "n8n-nodes-base.readWriteFile",
    "n8n-nodes-base.ssh",
}


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
            schema = json.loads(
                (ROOT / entry[schema_key]).read_text(encoding="utf-8")
            )
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
        if code == "simulate-user-block":
            names = {node.get("name") for node in workflow.get("nodes", [])}
            if not {"Claim Before Effect", "Report Synthetic Result"} <= names:
                raise ValueError(f"{path.name}: safe claim/callback chain is missing")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{code} {digest}")


if __name__ == "__main__":
    main()
