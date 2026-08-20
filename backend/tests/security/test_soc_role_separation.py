"""The SOC roles exist to keep decisions apart from the work they judge.

Before them a tenant had `tenant-admin`, which holds everything, and whatever
it had built for itself -- in the demo tenant a `viewer` role with no
permissions at all, which locked out the one user assigned to it. Segregation
of duties cannot be demonstrated when the only working role can do everything.

These assert the separations by name rather than by counting permissions, so a
future edit that hands an analyst the authority to close their own case fails
here and says why.
"""

import pytest
from sqlalchemy import text

from cyrvanta.shared.database import SessionFactory

ANALYST = "soc-analyst"
SUPERVISOR = "soc-supervisor"
AUDITOR = "auditor"


async def _permissions(role_code: str) -> set[str]:
    async with SessionFactory() as session, session.begin():
        await session.execute(text("SELECT set_config('app.auth_lookup', 'true', true)"))
        tenant = (await session.execute(text("SELECT id FROM tenants LIMIT 1"))).scalar()
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
            {"tenant": str(tenant)},
        )
        rows = await session.execute(
            text(
                """
                SELECT p.code FROM permissions p
                JOIN role_permissions rp ON rp.permission_id = p.id
                JOIN roles r ON r.id = rp.role_id
                WHERE r.code = :code
                """
            ),
            {"code": role_code},
        )
        return {row[0] for row in rows}


@pytest.mark.asyncio
async def test_the_soc_roles_exist_and_are_immutable() -> None:
    async with SessionFactory() as session, session.begin():
        await session.execute(text("SELECT set_config('app.auth_lookup', 'true', true)"))
        tenant = (await session.execute(text("SELECT id FROM tenants LIMIT 1"))).scalar()
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
            {"tenant": str(tenant)},
        )
        rows = await session.execute(
            text("SELECT code, is_system FROM roles WHERE code = ANY(:codes)"),
            {"codes": [ANALYST, SUPERVISOR, AUDITOR]},
        )
        seeded = dict(rows.all())

    assert set(seeded) == {ANALYST, SUPERVISOR, AUDITOR}
    # Immutable rather than merely protected: a tenant needing a different
    # combination clones the role, and the seeded one stays as the reference an
    # auditor can compare against.
    assert all(seeded.values()), "a SOC role was seeded as editable"


@pytest.mark.asyncio
async def test_an_analyst_may_resolve_but_never_close() -> None:
    """The separation the whole design rests on. Both used to require
    incident.close, so declaring an incident technically resolved needed the
    same authority as accepting that resolution.
    """
    analyst = await _permissions(ANALYST)
    assert "incident.resolve" in analyst
    assert "incident.close" not in analyst
    assert {"incident.resolve", "incident.close"} <= await _permissions(SUPERVISOR)


@pytest.mark.asyncio
async def test_the_hand_that_proposes_is_not_the_hand_that_approves() -> None:
    analyst = await _permissions(ANALYST)
    assert "response.request" in analyst
    assert "response.approve" not in analyst
    assert "response.approve" in await _permissions(SUPERVISOR)


@pytest.mark.asyncio
async def test_a_claim_is_assessed_by_someone_other_than_its_author() -> None:
    """`claim.assess` is described as assessing claims *independently*, which
    is not something the author of the claim can do to their own.
    """
    analyst = await _permissions(ANALYST)
    assert "claim.create" in analyst
    assert "claim.assess" not in analyst
    assert "claim.assess" in await _permissions(SUPERVISOR)


@pytest.mark.asyncio
async def test_an_analyst_does_not_choose_their_own_workload() -> None:
    assert "incident.assign" not in await _permissions(ANALYST)
    assert "incident.assign" in await _permissions(SUPERVISOR)


@pytest.mark.asyncio
async def test_an_auditor_can_read_everything_and_change_nothing() -> None:
    auditor = await _permissions(AUDITOR)
    assert {"incident.read", "audit.read", "claim.read", "response.read"} <= auditor
    # Listed rather than inferred from the verb: the catalogue says both `read`
    # and `view` for looking at something, so deciding whether a permission
    # mutates by reading its name would let a mutating one through the day
    # someone coins a third word for it.
    read_only_verbs = {"read", "view"}
    mutating = sorted(code for code in auditor if code.split(".")[-1] not in read_only_verbs)
    assert mutating == [], f"the auditor role grants something other than reading: {mutating}"


@pytest.mark.asyncio
async def test_a_supervisor_can_do_everything_an_analyst_can() -> None:
    """Supervision is the analyst's authority plus the judgements reserved for
    someone else, not a different and partly overlapping set.
    """
    assert await _permissions(ANALYST) <= await _permissions(SUPERVISOR)
