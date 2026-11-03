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


async def test_list_services_empty(client: AsyncClient) -> None:
    r = await client.get("/logs/services")
    assert r.status_code == 200
    assert r.json() == []


async def test_list_services_is_distinct_and_sorted(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    for service in ["checkout", "auth-api", "checkout", "billing", "auth-api"]:
        await _seed(
            session_factory,
            service=service,
            level="INFO",
            message="m",
            timestamp="2026-04-25T12:00:00Z",
        )

    r = await client.get("/logs/services")
    assert r.status_code == 200
    assert r.json() == ["auth-api", "billing", "checkout"]


async def _histogram(client: AsyncClient, **params: object) -> dict:
    r = await client.get("/logs/histogram", params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def test_histogram_empty_range_is_all_zeros(client: AsyncClient) -> None:
    body = await _histogram(
        client, start="2026-04-25T12:00:00Z", end="2026-04-25T13:00:00Z", buckets=4
    )
    assert body["total"] == 0
    assert len(body["buckets"]) == 4
    for b in body["buckets"]:
        assert b["counts"] == {
            "DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0
        }


async def test_histogram_boundaries_and_exclusive_end(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    # 4 buckets of 15 min over 12:00-13:00.
    for ts, level in [
        ("2026-04-25T12:00:00Z", "INFO"),  # start is inclusive -> bucket 0
        ("2026-04-25T12:14:59Z", "INFO"),  # last second of bucket 0
        ("2026-04-25T12:15:00Z", "ERROR"),  # boundary -> bucket 1
        ("2026-04-25T12:59:59Z", "DEBUG"),  # bucket 3
        ("2026-04-25T13:00:00Z", "INFO"),  # end is exclusive -> dropped
        ("2026-04-25T11:59:59Z", "INFO"),  # before start -> dropped
    ]:
        await _seed(
            session_factory, service="a", level=level, message="m", timestamp=ts
        )

    body = await _histogram(
        client, start="2026-04-25T12:00:00Z", end="2026-04-25T13:00:00Z", buckets=4
    )
    assert body["total"] == 4
    assert [b["counts"]["INFO"] for b in body["buckets"]] == [2, 0, 0, 0]
    assert [b["counts"]["ERROR"] for b in body["buckets"]] == [0, 1, 0, 0]
    assert [b["counts"]["DEBUG"] for b in body["buckets"]] == [0, 0, 0, 1]
    assert body["buckets"][0]["start"] == "2026-04-25T12:00:00Z"
    assert body["buckets"][1]["start"] == "2026-04-25T12:15:00Z"
    assert body["buckets"][3]["end"] == "2026-04-25T13:00:00Z"


async def test_histogram_filters_and_total_matches_counts(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    for service, level in [("a", "INFO"), ("a", "ERROR"), ("b", "ERROR"), ("a", "ERROR")]:
        await _seed(
            session_factory,
            service=service,
            level=level,
            message="m",
            timestamp="2026-04-25T12:30:00Z",
        )
    window = {"start": "2026-04-25T12:00:00Z", "end": "2026-04-25T13:00:00Z"}

    body = await _histogram(client, service="a", **window)
    assert body["total"] == 3

    body = await _histogram(client, service="a", level="ERROR", **window)
    assert body["total"] == 2
    assert sum(sum(b["counts"].values()) for b in body["buckets"]) == body["total"]


async def test_histogram_defaults_start_to_earliest_event(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed(
        session_factory, service="a", level="INFO", message="m",
        timestamp="2026-04-25T12:00:00Z",
    )
    await _seed(
        session_factory, service="a", level="INFO", message="m",
        timestamp="2026-04-25T12:30:00Z",
    )
    body = await _histogram(client, end="2026-04-25T13:00:00Z", buckets=2)
    assert body["buckets"][0]["start"] == "2026-04-25T12:00:00Z"
    assert body["total"] == 2


async def test_histogram_enforces_minimum_span(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed(
        session_factory, service="a", level="INFO", message="m",
        timestamp="2026-04-25T12:00:00Z",
    )
    body = await _histogram(
        client, start="2026-04-25T12:00:00Z", end="2026-04-25T12:00:01Z", buckets=2
    )
    assert body["buckets"][-1]["end"] == "2026-04-25T12:01:00Z"
    assert body["total"] == 1


async def test_histogram_rejects_bad_bucket_count(client: AsyncClient) -> None:
    for n in (0, 201):
        r = await client.get("/logs/histogram", params={"buckets": n})
        assert r.status_code == 422
