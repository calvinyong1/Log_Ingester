from collections.abc import AsyncIterator

import fakeredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import app
from app.queue import get_redis_connection
from app.worker.rate_limiter import ErrorRateTracker


@pytest.fixture
def redis_conn() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis()


@pytest_asyncio.fixture
async def rates_client(redis_conn: fakeredis.FakeRedis) -> AsyncIterator[AsyncClient]:
    # No require_api_key override: the endpoint must be open without one.
    app.dependency_overrides[get_redis_connection] = lambda: redis_conn
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()


async def test_no_keys_returns_empty_list(rates_client: AsyncClient) -> None:
    r = await rates_client.get("/services/error-rates")
    assert r.status_code == 200
    assert r.json()["services"] == []


async def test_counts_match_tracker_and_config_is_reported(
    rates_client: AsyncClient, redis_conn: fakeredis.FakeRedis
) -> None:
    settings = get_settings()
    tracker = ErrorRateTracker(redis_conn, settings.error_rate_window_seconds)
    for level in ["ERROR"] * 18 + ["INFO"] * 11:
        tracker.record("checkout", level)

    r = await rates_client.get("/services/error-rates")
    assert r.status_code == 200
    body = r.json()
    assert body["window_seconds"] == settings.error_rate_window_seconds
    assert body["threshold"] == settings.error_rate_threshold
    assert body["min_events"] == settings.error_rate_min_events
    assert body["services"] == [
        {"service": "checkout", "total": 29, "errors": 18, "error_rate": 0.6207}
    ]


async def test_service_without_errors_has_zero_rate(
    rates_client: AsyncClient, redis_conn: fakeredis.FakeRedis
) -> None:
    tracker = ErrorRateTracker(redis_conn, 300)
    tracker.record("auth-api", "INFO")
    tracker.record("auth-api", "DEBUG")

    r = await rates_client.get("/services/error-rates")
    assert r.json()["services"] == [
        {"service": "auth-api", "total": 2, "errors": 0, "error_rate": 0.0}
    ]


async def test_services_sorted_by_name(
    rates_client: AsyncClient, redis_conn: fakeredis.FakeRedis
) -> None:
    tracker = ErrorRateTracker(redis_conn, 300)
    for service in ["checkout", "auth-api", "billing"]:
        tracker.record(service, "INFO")

    r = await rates_client.get("/services/error-rates")
    names = [s["service"] for s in r.json()["services"]]
    assert names == ["auth-api", "billing", "checkout"]


async def test_endpoint_is_read_only(
    rates_client: AsyncClient, redis_conn: fakeredis.FakeRedis
) -> None:
    ErrorRateTracker(redis_conn, 300).record("checkout", "ERROR")
    before = {k: redis_conn.zrange(k, 0, -1) for k in redis_conn.keys("*")}

    await rates_client.get("/services/error-rates")

    after = {k: redis_conn.zrange(k, 0, -1) for k in redis_conn.keys("*")}
    assert before == after
