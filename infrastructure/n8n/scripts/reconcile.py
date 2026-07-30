import argparse
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_FIELDS = {"active", "createdAt", "id", "shared", "tags", "updatedAt", "versionId"}


def canonical_workflow(workflow: dict[str, Any]) -> bytes:
    material = {key: value for key, value in workflow.items() if key not in RUNTIME_FIELDS}
    return json.dumps(
        material, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()


def request_json(
    base_url: str,
    api_key: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    body = (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        if payload is not None
        else None
    )
    url = f"{base_url.rstrip('/')}{path}"
    if urllib.parse.urlsplit(url).scheme not in {"http", "https"}:
        raise RuntimeError("N8N_BASE_URL must use http or https")
    request = urllib.request.Request(  # noqa: S310 - scheme is restricted above
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-N8N-API-KEY": api_key,
        },
    )
    try:
        with urllib.request.urlopen(  # noqa: S310 - scheme is restricted above
            request, timeout=15
        ) as response:
            raw = response.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"n8n API request failed: {method} {path}") from exc
    return json.loads(raw) if raw else None


def reconcile(*, apply: bool) -> list[dict[str, object]]:
    base_url = os.environ.get("N8N_BASE_URL", "http://localhost:5678")
    api_key = os.environ.get("N8N_API_KEY", "")
    if not api_key:
        raise RuntimeError("N8N_API_KEY is required for reconciliation")
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    aliases = json.loads(os.environ.get("N8N_CREDENTIAL_ALIASES_JSON", "{}"))
    catalog = request_json(base_url, api_key, "GET", "/api/v1/workflows?limit=250")
    installed = {
        item["id"]: item
        for item in catalog.get("data", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    installed_by_name = {
        item["name"]: item
        for item in installed.values()
        if isinstance(item.get("name"), str)
    }
    results: list[dict[str, object]] = []
    managed_ids: set[str] = set()
    for entry in manifest["workflows"]:
        missing_aliases = [
            alias for alias in entry["credential_aliases"] if alias not in aliases
        ]
        should_activate = bool(entry["activate_by_default"])
        if apply and should_activate and missing_aliases:
            raise RuntimeError(
                f"{entry['code']}: unresolved credential aliases: {missing_aliases}"
            )
        source = json.loads((ROOT / entry["file"]).read_text(encoding="utf-8"))[0]
        configured_id = entry["n8n_id"]
        desired = hashlib.sha256(canonical_workflow(source)).hexdigest()
        current_summary = installed.get(configured_id) or installed_by_name.get(source["name"])
        if current_summary is None:
            workflow_id = configured_id
            action = "create"
            observed = None
        else:
            workflow_id = str(current_summary["id"])
            managed_ids.add(workflow_id)
            current = request_json(
                base_url, api_key, "GET", f"/api/v1/workflows/{workflow_id}"
            )
            observed = hashlib.sha256(canonical_workflow(current)).hexdigest()
            action = "unchanged" if observed == desired else "update"
        if apply and action in {"create", "update"}:
            writable = {
                key: value
                for key, value in source.items()
                if key not in {"active", "id", "tags", "versionId"}
            }
            if action == "create":
                created = request_json(
                    base_url, api_key, "POST", "/api/v1/workflows", writable
                )
                workflow_id = str(created["id"])
                managed_ids.add(workflow_id)
            else:
                request_json(
                    base_url,
                    api_key,
                    "PUT",
                    f"/api/v1/workflows/{workflow_id}",
                    writable,
                )
        if apply and should_activate:
            request_json(
                base_url, api_key, "POST", f"/api/v1/workflows/{workflow_id}/activate"
            )
        elif apply and workflow_id in installed:
            request_json(
                base_url, api_key, "POST", f"/api/v1/workflows/{workflow_id}/deactivate"
            )
        results.append(
            {
                "code": entry["code"],
                "workflow_id": workflow_id,
                "action": action,
                "desired_digest": desired,
                "observed_digest": observed,
                "activate": should_activate,
                "missing_credential_aliases": missing_aliases,
            }
        )
    unmanaged_cyrvanta = [
        workflow_id
        for workflow_id, workflow in installed.items()
        if workflow_id.startswith("cyrvanta-") and workflow_id not in managed_ids
    ]
    for workflow_id in unmanaged_cyrvanta:
        if apply:
            request_json(
                base_url, api_key, "POST", f"/api/v1/workflows/{workflow_id}/deactivate"
            )
        results.append(
            {
                "workflow_id": workflow_id,
                "action": "deactivate_unmanaged",
                "deleted": False,
            }
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply create/update/activation changes. Default is read-only diff.",
    )
    args = parser.parse_args()
    print(json.dumps(reconcile(apply=args.apply), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
