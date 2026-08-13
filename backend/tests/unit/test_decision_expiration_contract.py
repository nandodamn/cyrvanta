from pathlib import Path

from cyrvanta.modules.decision.application.service import DecisionService

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_decision_expiration_batch_fails_closed() -> None:
    service = DecisionService()
    coroutine = service.expire_due(batch_size=0)
    try:
        coroutine.send(None)
    except ValueError as exc:
        assert "between 1 and 500" in str(exc)
    else:
        raise AssertionError("invalid expiration batch size was accepted")
    finally:
        coroutine.close()


def test_scheduler_materializes_decision_expirations() -> None:
    scheduler = (BACKEND_ROOT / "src/cyrvanta/scheduler.py").read_text(encoding="utf-8")
    assert "await decisions.expire_due()" in scheduler


def test_expiration_discovery_is_restricted_and_bounded() -> None:
    migration = (
        BACKEND_ROOT / "alembic/versions/0022_decision_expiration_scheduler.py"
    ).read_text(encoding="utf-8")
    assert migration.count("SECURITY DEFINER") == 2
    assert "REVOKE ALL ON FUNCTION" in migration
    assert "p_limit < 1 OR p_limit > 500" in migration
    assert "status = 'PENDING'" in migration
    assert "status = 'ACTIVE'" in migration
