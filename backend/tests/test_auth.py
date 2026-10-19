from collections.abc import AsyncIterator
from unittest import mock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db import get_session
from app.main import app
from app.queue import get_queue

API_KEY = "test-key"
PAYLOAD = {"service": "auth-api", "level": "ERROR", "message": "boom"}


@pytest.fixture
def configured_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Set API_KEY for the test. get_settings() is cached, so clear it on the
    way in and out or the value leaks into (or out of) other tests."""
    monkeypatch.setenv("API_KEY", API_KEY)
    get_settings.cache_clear()
    yield API_KEY
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def auth_client(
    session_factory: async_sessionmaker[AsyncSession], fake_queue: mock.MagicMock
) -> AsyncIterator[AsyncClient]:
    """Like conftest's `client`, but without the require_api_key override, so
    the real check runs."""

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_queue] = lambda: fake_queue
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()


async def test_post_without_key_is_rejected(
    auth_client: AsyncClient, configured_key: str, fake_queue: mock.MagicMock
) -> None:
    r = await auth_client.post("/logs", json=PAYLOAD)
    assert r.status_code == 401
    fake_queue.enqueue.assert_not_called()


async def test_post_with_wrong_key_is_rejected(
    auth_client: AsyncClient, configured_key: str, fake_queue: mock.MagicMock
) -> None:
    r = await auth_client.post("/logs", json=PAYLOAD, headers={"X-API-Key": "nope"})
    assert r.status_code == 401
    fake_queue.enqueue.assert_not_called()


async def test_post_with_correct_key_is_accepted(
    auth_client: AsyncClient, configured_key: str, fake_queue: mock.MagicMock
) -> None:
    r = await auth_client.post("/logs", json=PAYLOAD, headers={"X-API-Key": API_KEY})
    assert r.status_code == 202, r.text
    fake_queue.enqueue.assert_called_once()


async def test_key_is_checked_before_body_validation(
    auth_client: AsyncClient, configured_key: str
) -> None:
    # An unauthenticated caller shouldn't learn the schema from 422 details.
    r = await auth_client.post("/logs", json={"service": ""})
    assert r.status_code == 401


async def test_fails_closed_when_server_key_unset(
    auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, fake_queue: mock.MagicMock
) -> None:
    monkeypatch.delenv("API_KEY", raising=False)
    get_settings.cache_clear()
    try:
        for headers in ({}, {"X-API-Key": ""}, {"X-API-Key": "anything"}):
            r = await auth_client.post("/logs", json=PAYLOAD, headers=headers)
            assert r.status_code == 401
    finally:
        get_settings.cache_clear()
    fake_queue.enqueue.assert_not_called()


async def test_fails_closed_when_server_key_empty(
    auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # What compose produces when ${API_KEY} isn't set anywhere.
    monkeypatch.setenv("API_KEY", "")
    get_settings.cache_clear()
    try:
        r = await auth_client.post("/logs", json=PAYLOAD, headers={"X-API-Key": ""})
        assert r.status_code == 401
    finally:
        get_settings.cache_clear()


async def test_get_logs_does_not_require_key(
    auth_client: AsyncClient, configured_key: str
) -> None:
    # Reads are public so the browser dashboard works without a secret.
    r = await auth_client.get("/logs")
    assert r.status_code == 200
