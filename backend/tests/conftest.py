from collections.abc import AsyncIterator
from unittest import mock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from rq import Queue
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.auth import require_api_key
from app.db import Base, get_session
from app.main import app
from app.queue import get_queue

# In-memory SQLite is fast and isolated per test session — fine for endpoint
# round-trips. Postgres-specific behaviour (timezones, indexes) is exercised in
# the docker-compose stack rather than here.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(test_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture
def fake_queue() -> mock.MagicMock:
    """POST /logs only needs to prove it enqueued the right job — actually
    running it is the worker's own tests' job (see test_worker.py)."""
    return mock.MagicMock(spec=Queue)


@pytest_asyncio.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession], fake_queue: mock.MagicMock
) -> AsyncIterator[AsyncClient]:
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_queue] = lambda: fake_queue
    # Endpoint tests are about request/response behaviour, not auth, so skip
    # the API key check here. Auth itself gets dedicated tests.
    app.dependency_overrides[require_api_key] = lambda: None
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
