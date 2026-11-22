from datetime import UTC, datetime, timedelta
from unittest import mock

import fakeredis
import redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.metrics import render
from app.models import Alert, LogEvent
from app.worker.prune import prune_and_record, prune_old_rows

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)


def _event(age: timedelta, received_age: timedelta | None = None) -> LogEvent:
    return LogEvent(
        service="svc",
        level="INFO",
        message="m",
        timestamp=NOW - age,
        received_at=NOW - (received_age if received_age is not None else age),
    )


def _alert(age: timedelta) -> Alert:
    return Alert(
        service="svc",
        fired_at=NOW - age,
        window_seconds=300,
        total=10,
        errors=9,
        error_rate=0.9,
        threshold=0.5,
    )


async def _count(factory: async_sessionmaker[AsyncSession], model) -> int:
    async with factory() as session:
        return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def _seed(factory: async_sessionmaker[AsyncSession], *rows) -> None:
    async with factory() as session:
        session.add_all(rows)
        await session.commit()


async def test_deletes_only_rows_older_than_retention(session_factory) -> None:
    await _seed(
        session_factory,
        _event(timedelta(days=11)),
        _event(timedelta(days=9)),
        _alert(timedelta(days=11)),
        _alert(timedelta(days=9)),
    )

    result = await prune_old_rows(session_factory=session_factory, now=NOW, retention_days=10)

    assert result == {"log_events": 1, "alerts": 1}
    assert await _count(session_factory, LogEvent) == 1
    assert await _count(session_factory, Alert) == 1


async def test_row_exactly_at_cutoff_is_kept(session_factory) -> None:
    await _seed(session_factory, _event(timedelta(days=10)), _alert(timedelta(days=10)))

    result = await prune_old_rows(session_factory=session_factory, now=NOW, retention_days=10)

    assert result == {"log_events": 0, "alerts": 0}
    assert await _count(session_factory, LogEvent) == 1
    assert await _count(session_factory, Alert) == 1


async def test_batches_delete_everything(session_factory) -> None:
    await _seed(session_factory, *[_event(timedelta(days=20)) for _ in range(5)])

    result = await prune_old_rows(
        session_factory=session_factory, now=NOW, retention_days=10, batch_size=2
    )

    assert result["log_events"] == 5
    assert await _count(session_factory, LogEvent) == 0


async def test_zero_retention_deletes_nothing(session_factory) -> None:
    await _seed(session_factory, _event(timedelta(days=400)), _alert(timedelta(days=400)))

    result = await prune_old_rows(session_factory=session_factory, now=NOW, retention_days=0)

    assert result == {"log_events": 0, "alerts": 0}
    assert await _count(session_factory, LogEvent) == 1
    assert await _count(session_factory, Alert) == 1


async def test_uses_event_time_not_received_at(session_factory) -> None:
    await _seed(session_factory, _event(timedelta(days=20), received_age=timedelta(minutes=1)))

    result = await prune_old_rows(session_factory=session_factory, now=NOW, retention_days=10)

    assert result["log_events"] == 1


async def test_prune_and_record_reports_deleted_rows_to_metrics(session_factory) -> None:
    redis_conn = fakeredis.FakeStrictRedis()
    await _seed(session_factory, _event(timedelta(days=400)), _alert(timedelta(days=400)))

    result = await prune_and_record(session_factory=session_factory, redis_conn=redis_conn)

    assert result == {"log_events": 1, "alerts": 1}
    output = render(redis_conn).decode()
    assert 'rows_pruned_total{table="log_events"} 1.0' in output
    assert 'rows_pruned_total{table="alerts"} 1.0' in output


async def test_redis_failure_does_not_fail_the_prune(session_factory) -> None:
    broken = mock.MagicMock()
    broken.pipeline.side_effect = redis.exceptions.RedisError("down")
    broken.hincrby.side_effect = redis.exceptions.RedisError("down")
    await _seed(session_factory, _event(timedelta(days=400)))

    result = await prune_and_record(session_factory=session_factory, redis_conn=broken)

    assert result["log_events"] == 1
    assert await _count(session_factory, LogEvent) == 0
