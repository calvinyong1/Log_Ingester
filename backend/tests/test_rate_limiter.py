import fakeredis

from app.worker.rate_limiter import ErrorRateTracker


def test_record_counts_within_window() -> None:
    conn = fakeredis.FakeStrictRedis()
    tracker = ErrorRateTracker(conn, window_seconds=60)

    counts = tracker.record("svc", "INFO", now=1000)
    assert counts.total == 1
    assert counts.errors == 0

    counts = tracker.record("svc", "ERROR", now=1010)
    assert counts.total == 2
    assert counts.errors == 1
    assert counts.error_rate == 0.5


def test_record_trims_entries_outside_window() -> None:
    conn = fakeredis.FakeStrictRedis()
    tracker = ErrorRateTracker(conn, window_seconds=60)

    tracker.record("svc", "ERROR", now=1000)
    counts = tracker.record("svc", "INFO", now=1100)  # 100s later, window is 60s

    assert counts.total == 1  # the t=1000 ERROR aged out
    assert counts.errors == 0


def test_counts_are_isolated_per_service() -> None:
    conn = fakeredis.FakeStrictRedis()
    tracker = ErrorRateTracker(conn, window_seconds=60)

    tracker.record("svc-a", "ERROR", now=1000)
    counts = tracker.record("svc-b", "INFO", now=1000)

    assert counts.total == 1
    assert counts.errors == 0


def test_alert_cooldown_blocks_repeat_within_window() -> None:
    conn = fakeredis.FakeStrictRedis()
    tracker = ErrorRateTracker(conn, window_seconds=60)

    assert tracker.acquire_alert_cooldown("svc", cooldown_seconds=30) is True
    assert tracker.acquire_alert_cooldown("svc", cooldown_seconds=30) is False
