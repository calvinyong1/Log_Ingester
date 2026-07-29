import asyncio
import uuid

import pytest
import redis as redis_lib
from rq import Queue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import LogEvent
from app.queue import get_redis_connection


def _redis_reachable() -> bool:
    try:
        conn = redis_lib.from_url(get_settings().redis_url, socket_connect_timeout=1)
        conn.ping()
        return True
    except redis_lib.RedisError:
        return False
    except OSError:
        return False


# Only meaningful with a real Redis + Postgres + a live worker process, i.e.
# run via `docker compose exec api uv run pytest -q` where the `worker`
# service is already consuming the same queue. Auto-skips otherwise so the
# plain local `pytest -q` (sqlite, no redis) stays green.
pytestmark = pytest.mark.skipif(
    not _redis_reachable(), reason="requires live Redis + Postgres (run inside docker compose)"
)


async def test_enqueued_job_is_processed_by_the_live_worker() -> None:
    """Enqueues onto the real "ingest" queue and waits for the compose
    `worker` service — a separate, already-running process — to pick it up
    and persist it. Deliberately does not run its own consumer: a competing
    consumer would race the real worker for the same job."""
    settings = get_settings()
    queue = Queue("ingest", connection=get_redis_connection())

    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    service = f"itest-{uuid.uuid4().hex[:8]}"
    queue.enqueue(
        "app.worker.tasks.process_log_event",
        {
            "service": service,
            "level": "INFO",
            "message": "integration check",
            "timestamp": "2026-07-15T00:00:00Z",
        },
    )

    rows = []
    for _ in range(20):  # up to ~10s for the live worker to process the job
        async with session_factory() as session:
            rows = (
                (await session.execute(select(LogEvent).where(LogEvent.service == service)))
                .scalars()
                .all()
            )
        if rows:
            break
        await asyncio.sleep(0.5)
    await engine.dispose()

    assert len(rows) == 1
    assert rows[0].message == "integration check"
