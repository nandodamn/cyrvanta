import json
from pathlib import Path
from typing import Any

from cyrvanta.modules.playbooks.application.portable import PortablePlaybookV1

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "schemas" / "playbook-v1.schema.json"


def build_schema() -> dict[str, Any]:
    generated = PortablePlaybookV1.model_json_schema(mode="validation")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:cyrvanta:playbook:1.0",
        **generated,
    }


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(build_schema(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
