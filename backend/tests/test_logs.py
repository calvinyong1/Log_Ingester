from datetime import datetime
from unittest import mock

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import LogEvent


async def _seed(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    service: str,
    level: str,
    message: str,
    timestamp: str,
) -> None:
    async with session_factory() as session:
        session.add(
            LogEvent(
                service=service,
                level=level,
                message=message,
                timestamp=datetime.fromisoformat(timestamp.replace("Z", "+00:00")),
            )
        )
        await session.commit()


async def test_ingest_returns_202_and_queues_job(
    client: AsyncClient, fake_queue: mock.MagicMock
) -> None:
    r = await client.post(
        "/logs",
        json={
            "service": "auth-api",
            "level": "ERROR",
            "message": "boom",
            "timestamp": "2026-04-25T12:00:00Z",
        },
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert body["service"] == "auth-api"
    assert body["level"] == "ERROR"
    assert body["message"] == "boom"
    assert body["timestamp"] == "2026-04-25T12:00:00Z"

    fake_queue.enqueue.assert_called_once()
    (job_path, job_payload), _ = fake_queue.enqueue.call_args
    assert job_path == "app.worker.tasks.process_log_event"
    assert job_payload["service"] == "auth-api"
    assert job_payload["level"] == "ERROR"
    assert job_payload["message"] == "boom"


async def test_ingest_rejects_unknown_level(client: AsyncClient) -> None:
    r = await client.post(
        "/logs",
        json={"service": "x", "level": "TRACE", "message": "hi"},
    )
    assert r.status_code == 422


async def test_ingest_fills_timestamp_when_missing(client: AsyncClient) -> None:
    r = await client.post(
        "/logs",
        json={"service": "x", "level": "INFO", "message": "hi"},
    )
    assert r.status_code == 202
    assert r.json()["timestamp"] is not None


async def test_list_filters_and_orders(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed(
        session_factory, service="a", level="INFO", message="m1", timestamp="2026-04-25T10:00:00Z"
    )
    await _seed(
        session_factory,
        service="a",
        level="ERROR",
        message="m2",
        timestamp="2026-04-25T11:00:00Z",
    )
    await _seed(
        session_factory,
        service="b",
        level="ERROR",
        message="m3",
        timestamp="2026-04-25T12:00:00Z",
    )

    # No filters: newest first.
    r = await client.get("/logs")
    assert r.status_code == 200
    page = r.json()
    assert page["total"] == 3
    assert [item["message"] for item in page["items"]] == ["m3", "m2", "m1"]

    # Filter by service.
    r = await client.get("/logs", params={"service": "a"})
    page = r.json()
    assert page["total"] == 2
    assert {item["message"] for item in page["items"]} == {"m1", "m2"}

    # Filter by level.
    r = await client.get("/logs", params={"level": "ERROR"})
    page = r.json()
    assert page["total"] == 2
    assert {item["message"] for item in page["items"]} == {"m2", "m3"}

    # Time-range filter is [start, end).
    r = await client.get(
        "/logs",
        params={"start": "2026-04-25T11:00:00Z", "end": "2026-04-25T12:00:00Z"},
    )
    page = r.json()
    assert page["total"] == 1
    assert page["items"][0]["message"] == "m2"


async def test_list_paginates(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    for i in range(5):
        await _seed(
            session_factory,
            service="svc",
            level="INFO",
            message=f"m{i}",
            timestamp=f"2026-04-25T10:0{i}:00Z",
        )

    r = await client.get("/logs", params={"limit": 2, "offset": 0})
    page = r.json()
    assert page["total"] == 5
    assert len(page["items"]) == 2
    assert page["items"][0]["message"] == "m4"  # newest
    assert page["items"][1]["message"] == "m3"

    r = await client.get("/logs", params={"limit": 2, "offset": 2})
    page = r.json()
    assert [item["message"] for item in page["items"]] == ["m2", "m1"]


async def test_health(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
