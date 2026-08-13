import ast
import re
from pathlib import Path

from cyrvanta import worker


EVENT_NAME = re.compile(r"^(?:security|knowledge|platform)\.[a-z0-9_.]+$")


def test_every_production_event_name_is_routed_by_the_worker() -> None:
    source_root = Path(worker.__file__).resolve().parent
    discovered: set[str] = set()
    for path in source_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        discovered.update(
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and EVENT_NAME.fullmatch(node.value)
        )

    assert discovered <= worker.WORKER_EVENT_NAMES


def test_observational_registry_excludes_events_with_downstream_effects() -> None:
    assert worker.FINDING_NORMALIZED_EVENT not in worker.OBSERVED_EVENT_NAMES
    assert worker.CORRELATION_MATCHED_EVENT not in worker.OBSERVED_EVENT_NAMES
    assert worker.CORRELATION_MEMBER_ADDED_EVENT not in worker.OBSERVED_EVENT_NAMES
    assert worker.DISPATCH_REQUESTED_EVENT not in worker.OBSERVED_EVENT_NAMES
