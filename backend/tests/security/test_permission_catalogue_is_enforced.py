"""Every permission the catalogue offers must be enforced by something.

A permission nobody checks grants nothing, which sounds harmless and is not.
It is offered in the administration screen as though it enabled a capability,
so an operator can grant it believing it does something. Worse is what happens
afterwards: when the feature it was named for finally ships, a grant made long
ago and never reviewed becomes live, and the authorization is inherited from a
decision nobody remembers making.

Eleven such permissions accumulated across phases 18 to 21A -- seeded by
approved specifications whose code never landed -- and nine of them were
already granted. Migration 0025 retired them. This keeps the catalogue and the
code from drifting apart again: seed a permission and something must require
it, or the seed does not belong yet.
"""

from pathlib import Path

import pytest
from sqlalchemy import text

from cyrvanta.shared.database import SessionFactory

SOURCE_ROOT = Path(__file__).parents[2] / "src" / "cyrvanta"


def _source_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in SOURCE_ROOT.rglob("*.py"))


@pytest.mark.asyncio
async def test_every_seeded_permission_is_referenced_by_the_code() -> None:
    async with SessionFactory() as session, session.begin():
        codes = list(
            (await session.scalars(text("SELECT code FROM permissions ORDER BY code"))).all()
        )

    assert codes, "the permission catalogue is empty; the seed migrations did not run"

    source = _source_text()
    # Referenced anywhere in the backend, not only in require_permission():
    # some are selected dynamically (incident.close is chosen from the target
    # status), so demanding a literal call would report those as unused.
    unenforced = sorted(code for code in codes if f'"{code}"' not in source)

    assert unenforced == [], (
        "these permissions are offered by the catalogue but no code requires them, "
        "so granting one gives an operator a capability that does not exist yet: "
        f"{unenforced}"
    )
