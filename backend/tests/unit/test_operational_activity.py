from datetime import UTC, datetime, timedelta

from cyrvanta.modules.operations.application.activity import build_activity_24h


def test_activity_empty_has_twelve_zero_buckets() -> None:
    now = datetime(2026, 8, 1, 12, tzinfo=UTC)
    result = build_activity_24h(alert_rows=[], incident_rows=[], now=now)

    assert result.source_mode == "EMPTY"
    assert result.totals.alerts == 0
    assert result.totals.incidents == 0
    assert len(result.series) == 12
    assert result.window_start == now - timedelta(hours=24)
    assert all(bucket.alerts == bucket.incidents == 0 for bucket in result.series)


def test_activity_uses_window_boundaries_and_never_invents_counts() -> None:
    now = datetime(2026, 8, 1, 12, tzinfo=UTC)
    result = build_activity_24h(
        alert_rows=[
            (now - timedelta(hours=24), True),
            (now - timedelta(hours=1), False),
            (now - timedelta(hours=25), False),
        ],
        incident_rows=[(now, False)],
        now=now,
    )

    assert result.source_mode == "MIXED"
    assert result.totals.alerts == 2
    assert result.totals.incidents == 1
    assert result.series[0].alerts == 1
    assert result.series[-1].alerts == 1
    assert result.series[-1].incidents == 1


def test_activity_source_modes_are_derived_from_records() -> None:
    now = datetime(2026, 8, 1, 12, tzinfo=UTC)
    simulated = build_activity_24h(alert_rows=[(now, True)], incident_rows=[], now=now)
    live = build_activity_24h(alert_rows=[], incident_rows=[(now, False)], now=now)

    assert simulated.source_mode == "SIMULATED"
    assert live.source_mode == "LIVE"
