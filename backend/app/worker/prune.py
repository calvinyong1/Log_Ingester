import logging
from datetime import UTC, datetime, timedelta

import redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import InstrumentedAttribute

from app.config import get_settings
from app.db import SessionLocal
from app.metrics import record_pruned
from app.models import Alert, LogEvent
from app.queue import get_redis_connection

logger = logging.getLogger("app.worker.prune")

# Event time, not received_at: the retention period is about how old the data is,
# and received_at only measures how long the event took to be persisted.
_PRUNED_COLUMNS: dict[str, tuple[type, InstrumentedAttribute]] = {
    "log_events": (LogEvent, LogEvent.timestamp),
    "alerts": (Alert, Alert.fired_at),
}


async def prune_old_rows(
    *,
    session_factory: async_sessionmaker | None = None,
    now: datetime | None = None,
    retention_days: int | None = None,
    batch_size: int | None = None,
) -> dict[str, int]:
    """Delete log_events and alerts strictly older than the retention period.

    Returns the rows deleted per table. A retention of 0 or less deletes nothing.
    """
    settings = get_settings()
    retention_days = settings.retention_days if retention_days is None else retention_days
    batch_size = settings.prune_batch_size if batch_size is None else batch_size
    deleted = dict.fromkeys(_PRUNED_COLUMNS, 0)
    if retention_days <= 0:
        return deleted

    factory = session_factory or SessionLocal
    cutoff = (now or datetime.now(UTC)) - timedelta(days=retention_days)
    for table, (model, column) in _PRUNED_COLUMNS.items():
        while True:
            # Subquery with LIMIT because Postgres has no DELETE ... LIMIT.
            batch = select(model.id).where(column < cutoff).order_by(model.id).limit(batch_size)
            async with factory() as session:
                result = await session.execute(delete(model).where(model.id.in_(batch)))
                await session.commit()
            deleted[table] += result.rowcount
            if result.rowcount < batch_size:
                break

    logger.info("Pruned rows older than %s days: %s", retention_days, deleted)
    return deleted


async def prune_and_record(
    *, session_factory: async_sessionmaker | None = None, redis_conn=None
) -> dict[str, int]:
    deleted = await prune_old_rows(session_factory=session_factory)
    # Metrics must never fail the job: the rows are already gone, and a retry
    # would only find nothing to count.
    try:
        conn = redis_conn if redis_conn is not None else get_redis_connection()
        for table, count in deleted.items():
            if count:
                record_pruned(conn, table, count)
    except redis.exceptions.RedisError:
        logger.warning("Could not record pruned row counts", exc_info=True)
    return deleted
