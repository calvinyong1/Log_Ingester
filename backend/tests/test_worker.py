from datetime import UTC, datetime

import fakeredis
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.logging_config import request_id_var
from app.models import Alert, LogEvent
from app.worker.tasks import process_log_event


def _payload(service: str = "svc", level: str = "INFO", message: str = "hi") -> dict:
    return {
        "service": service,
        "level": level,
        "message": message,
        "timestamp": datetime.now(UTC).isoformat(),
    }


async def test_process_log_event_persists_to_db(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    redis_conn = fakeredis.FakeStrictRedis()

    await process_log_event(
        _payload(service="checkout"),
        session_factory=session_factory,
        redis_conn=redis_conn,
    )

    async with session_factory() as session:
        rows = (await session.execute(select(LogEvent))).scalars().all()
    assert len(rows) == 1
    assert rows[0].service == "checkout"


async def test_low_volume_does_not_alert(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    redis_conn = fakeredis.FakeStrictRedis()
    alerts: list[dict] = []
    monkeypatch.setattr("app.worker.tasks.send_alert", lambda **kwargs: alerts.append(kwargs))

    # Default error_rate_min_events is 5 — 3 errors shouldn't be enough to alert.
    for _ in range(3):
        await process_log_event(
            _payload(service="checkout", level="ERROR"),
            session_factory=session_factory,
            redis_conn=redis_conn,
        )

    assert alerts == []


async def test_error_rate_above_threshold_triggers_alert(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    redis_conn = fakeredis.FakeStrictRedis()
    alerts: list[dict] = []
    monkeypatch.setattr("app.worker.tasks.send_alert", lambda **kwargs: alerts.append(kwargs))

    # Default: min_events=5, threshold=0.5 -> 3/5 errors should trip it.
    for level in ["ERROR", "ERROR", "ERROR", "INFO", "INFO"]:
        await process_log_event(
            _payload(service="checkout", level=level),
            session_factory=session_factory,
            redis_conn=redis_conn,
        )

    assert len(alerts) == 1
    assert alerts[0]["service"] == "checkout"
    assert alerts[0]["total"] == 5
    assert alerts[0]["errors"] == 3


async def test_alert_respects_cooldown(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    redis_conn = fakeredis.FakeStrictRedis()
    alerts: list[dict] = []
    monkeypatch.setattr("app.worker.tasks.send_alert", lambda **kwargs: alerts.append(kwargs))

    for _ in range(10):
        await process_log_event(
            _payload(service="checkout", level="ERROR"),
            session_factory=session_factory,
            redis_conn=redis_conn,
        )

    assert len(alerts) == 1  # cooldown suppresses the repeats


async def _alerts(session_factory: async_sessionmaker[AsyncSession]) -> list[Alert]:
    async with session_factory() as session:
        return list((await session.execute(select(Alert))).scalars().all())


async def test_alert_is_saved_with_the_numbers_that_tripped_it(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    redis_conn = fakeredis.FakeStrictRedis()
    monkeypatch.setattr("app.worker.tasks.send_alert", lambda **kwargs: None)

    for level in ["ERROR", "ERROR", "ERROR", "INFO", "INFO"]:
        await process_log_event(
            _payload(service="checkout", level=level),
            session_factory=session_factory,
            redis_conn=redis_conn,
        )

    (alert,) = await _alerts(session_factory)
    assert (alert.service, alert.total, alert.errors) == ("checkout", 5, 3)
    assert alert.error_rate == pytest.approx(0.6)
    assert alert.threshold == 0.5
    assert alert.window_seconds == 300


async def test_no_alert_row_below_threshold_or_during_cooldown(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.worker.tasks.send_alert", lambda **kwargs: None)

    low = fakeredis.FakeStrictRedis()
    for _ in range(3):  # under min_events
        await process_log_event(
            _payload(service="quiet", level="ERROR"),
            session_factory=session_factory,
            redis_conn=low,
        )
    assert await _alerts(session_factory) == []

    hot = fakeredis.FakeStrictRedis()
    for _ in range(10):  # cooldown allows one alert, so one row
        await process_log_event(
            _payload(service="checkout", level="ERROR"),
            session_factory=session_factory,
            redis_conn=hot,
        )
    assert len(await _alerts(session_factory)) == 1


def _fail_alert_inserts(monkeypatch: pytest.MonkeyPatch, times: int) -> None:
    real_alert = Alert
    calls = {"n": 0}

    def flaky(**kwargs: object) -> Alert:
        calls["n"] += 1
        if calls["n"] <= times:
            raise RuntimeError("db down")
        return real_alert(**kwargs)

    monkeypatch.setattr("app.worker.tasks.Alert", flaky)


async def _error_burst(
    session_factory: async_sessionmaker[AsyncSession], redis_conn: fakeredis.FakeStrictRedis, n: int
) -> None:
    for _ in range(n):
        await process_log_event(
            _payload(service="checkout", level="ERROR"),
            session_factory=session_factory,
            redis_conn=redis_conn,
        )


async def test_failed_alert_insert_releases_cooldown_and_sends_nothing(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[dict] = []
    monkeypatch.setattr("app.worker.tasks.send_alert", lambda **kwargs: sent.append(kwargs))
    _fail_alert_inserts(monkeypatch, times=1)
    redis_conn = fakeredis.FakeStrictRedis()

    await _error_burst(session_factory, redis_conn, 5)

    assert sent == []
    assert await _alerts(session_factory) == []
    assert redis_conn.exists("alert_cooldown:checkout") == 0


async def test_alert_is_sent_once_the_insert_works_again_after_a_failure(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[dict] = []
    monkeypatch.setattr("app.worker.tasks.send_alert", lambda **kwargs: sent.append(kwargs))
    _fail_alert_inserts(monkeypatch, times=1)
    redis_conn = fakeredis.FakeStrictRedis()

    await _error_burst(session_factory, redis_conn, 6)

    assert len(sent) == 1
    assert len(await _alerts(session_factory)) == 1


async def test_alert_args_carry_the_saved_row_id_and_fired_at(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[dict] = []
    monkeypatch.setattr("app.worker.tasks.send_alert", lambda **kwargs: sent.append(kwargs))

    await _error_burst(session_factory, fakeredis.FakeStrictRedis(), 5)

    (alert,) = await _alerts(session_factory)
    assert sent[0]["alert_id"] == alert.id
    assert sent[0]["fired_at"] == alert.fired_at.replace(tzinfo=sent[0]["fired_at"].tzinfo)
    assert sent[0]["fired_at"].tzinfo is not None


@pytest.fixture
def webhook_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://example.com/hook")
    get_settings.cache_clear()
    yield
    monkeypatch.undo()
    get_settings.cache_clear()


async def test_webhook_failure_keeps_cooldown_and_does_not_raise(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    webhook_env: None,
) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise httpx.ConnectError("down")

    monkeypatch.setattr("app.worker.alerts.httpx.post", refuse)
    monkeypatch.setattr("app.worker.alerts.time.sleep", lambda _: None)
    redis_conn = fakeredis.FakeStrictRedis()

    await _error_burst(session_factory, redis_conn, 5)

    assert len(await _alerts(session_factory)) == 1
    assert redis_conn.exists("alert_cooldown:checkout") == 1


async def test_redelivered_event_is_stored_once_but_still_counted(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # A retry after the DB commit but before the Redis write must not duplicate
    # the row, and must still reach the rolling window it missed the first time.
    redis_conn = fakeredis.FakeStrictRedis()
    payload = {**_payload(service="checkout"), "event_id": "evt-1"}

    await process_log_event(payload, session_factory=session_factory, redis_conn=redis_conn)
    redis_conn.flushall()  # simulate the Redis write that never happened
    await process_log_event(payload, session_factory=session_factory, redis_conn=redis_conn)

    async with session_factory() as session:
        rows = (await session.execute(select(LogEvent))).scalars().all()
    assert len(rows) == 1
    assert redis_conn.zcard("events:checkout") == 1


async def test_redelivered_event_that_redis_already_has_is_not_counted_twice(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # A retry after a later step failed (or a client resending the same id)
    # must not inflate the rolling window.
    redis_conn = fakeredis.FakeStrictRedis()
    payload = {**_payload(service="checkout", level="ERROR"), "event_id": "evt-2"}

    await process_log_event(payload, session_factory=session_factory, redis_conn=redis_conn)
    await process_log_event(payload, session_factory=session_factory, redis_conn=redis_conn)

    assert redis_conn.zcard("events:checkout") == 1
    assert redis_conn.zcard("errors:checkout") == 1


async def test_job_sets_the_request_id_from_the_payload_and_resets_it(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str | None] = []
    monkeypatch.setattr(
        "app.worker.tasks.send_alert", lambda **kwargs: seen.append(request_id_var.get())
    )
    redis_conn = fakeredis.FakeStrictRedis()

    for _ in range(5):
        await process_log_event(
            {**_payload(service="checkout", level="ERROR"), "request_id": "req-9"},
            session_factory=session_factory,
            redis_conn=redis_conn,
        )

    assert seen == ["req-9"]
    assert request_id_var.get() is None


async def test_job_without_a_request_id_still_runs(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await process_log_event(
        _payload(service="checkout"),
        session_factory=session_factory,
        redis_conn=fakeredis.FakeStrictRedis(),
    )

    async with session_factory() as session:
        assert len((await session.execute(select(LogEvent))).scalars().all()) == 1
