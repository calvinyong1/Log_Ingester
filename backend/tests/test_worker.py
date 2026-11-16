from datetime import UTC, datetime

import fakeredis
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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


async def test_failed_alert_save_does_not_swallow_the_alert(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[dict] = []
    monkeypatch.setattr("app.worker.tasks.send_alert", lambda **kwargs: sent.append(kwargs))

    def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr("app.worker.tasks.Alert", broken)

    redis_conn = fakeredis.FakeStrictRedis()
    for _ in range(5):
        await process_log_event(
            _payload(service="checkout", level="ERROR"),
            session_factory=session_factory,
            redis_conn=redis_conn,
        )

    assert len(sent) == 1
    assert await _alerts(session_factory) == []
