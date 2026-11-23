import logging
from datetime import UTC, datetime, timedelta

import redis
from rq import Queue
from rq.job import Job
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import InstrumentedAttribute

from app.config import get_settings
from app.db import SessionLocal
from app.metrics import record_pruned
from app.models import Alert, LogEvent
from app.queue import get_queue, get_redis_connection

logger = logging.getLogger("app.worker.prune")

PRUNE_JOB_PATH = "app.worker.prune.run_prune_job"

# One run does at most this many batches per table, then hands the worker back:
# the prune shares the only worker with ingest, so an unbounded run (first run on
# a big table, catching up after downtime) would stall every job queued behind it.
PRUNE_MAX_BATCHES_PER_RUN = 20
# When a run hit that cap there is probably more to delete, so it comes back soon
# instead of waiting a whole PRUNE_INTERVAL_SECONDS.
PRUNE_CATCHUP_DELAY_SECONDS = 10

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
    max_batches: int | None = None,
) -> dict[str, int]:
    """Delete log_events and alerts strictly older than the retention period.

    Returns the rows deleted per table. A retention of 0 or less deletes nothing;
    each table stops after `max_batches` batches (default PRUNE_MAX_BATCHES_PER_RUN).
    """
    settings = get_settings()
    retention_days = settings.retention_days if retention_days is None else retention_days
    batch_size = settings.prune_batch_size if batch_size is None else batch_size
    max_batches = PRUNE_MAX_BATCHES_PER_RUN if max_batches is None else max_batches
    deleted = dict.fromkeys(_PRUNED_COLUMNS, 0)
    if retention_days <= 0:
        return deleted

    factory = session_factory or SessionLocal
    cutoff = (now or datetime.now(UTC)) - timedelta(days=retention_days)
    for table, (model, column) in _PRUNED_COLUMNS.items():
        for _ in range(max_batches):
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


def schedule_next_prune(
    queue: Queue | None = None, delay_seconds: int | None = None
) -> Job | None:
    settings = get_settings()
    if settings.retention_days <= 0:
        return None
    queue = queue or get_queue()
    # A fresh job id each run, not one fixed id: the running job's own status
    # write at completion would overwrite a successor scheduled under its id.
    delay = settings.prune_interval_seconds if delay_seconds is None else delay_seconds
    return queue.enqueue_in(
        timedelta(seconds=delay), PRUNE_JOB_PATH, job_timeout=settings.job_timeout_seconds
    )


def ensure_prune_scheduled(queue: Queue | None = None) -> bool:
    """Start the prune chain unless one is already waiting; called at worker startup.

    Only scheduled and queued jobs count: a "started" entry left by a killed worker
    would otherwise block the chain forever. With several workers starting at once
    two chains could form, which is harmless (deletes are idempotent) but wasteful.
    """
    if get_settings().retention_days <= 0:
        return False
    queue = queue or get_queue()
    waiting = [*queue.scheduled_job_registry.get_job_ids(), *queue.get_job_ids()]
    for job in Job.fetch_many(waiting, connection=queue.connection):
        if job is not None and job.func_name == PRUNE_JOB_PATH:
            return False
    return schedule_next_prune(queue) is not None


async def run_prune_job(
    *,
    session_factory: async_sessionmaker | None = None,
    redis_conn=None,
    queue: Queue | None = None,
) -> None:
    """The RQ job: prune, then schedule the next run even if this one failed."""
    caught_up = True
    try:
        deleted = await prune_and_record(session_factory=session_factory, redis_conn=redis_conn)
        cap = PRUNE_MAX_BATCHES_PER_RUN * get_settings().prune_batch_size
        caught_up = all(count < cap for count in deleted.values())
    finally:
        schedule_next_prune(queue, None if caught_up else PRUNE_CATCHUP_DELAY_SECONDS)
