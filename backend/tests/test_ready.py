from unittest import mock

import redis
from httpx import AsyncClient

from app.main import app
from app.queue import get_redis_connection


async def test_ready_ok_when_dependencies_respond(client: AsyncClient) -> None:
    app.dependency_overrides[get_redis_connection] = lambda: mock.MagicMock(spec=redis.Redis)

    r = await client.get("/ready")

    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


async def test_ready_503_when_redis_is_down(client: AsyncClient) -> None:
    broken = mock.MagicMock(spec=redis.Redis)
    broken.ping.side_effect = redis.ConnectionError("down")
    app.dependency_overrides[get_redis_connection] = lambda: broken

    r = await client.get("/ready")

    assert r.status_code == 503
