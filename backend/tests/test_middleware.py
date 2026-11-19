import logging
import re

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.logging_config import request_id_var
from app.middleware import RequestContextMiddleware


async def test_response_has_generated_request_id_header(client: AsyncClient) -> None:
    r = await client.get("/health")

    assert re.fullmatch(r"[0-9a-f]{32}", r.headers["X-Request-ID"])


async def test_valid_incoming_request_id_is_echoed(client: AsyncClient) -> None:
    r = await client.get("/health", headers={"X-Request-ID": "req-123.a:b"})

    assert r.headers["X-Request-ID"] == "req-123.a:b"


@pytest.mark.parametrize("bad_id", ["has space", "x" * 65, ""])
async def test_malformed_incoming_request_id_is_replaced(
    client: AsyncClient, bad_id: str
) -> None:
    r = await client.get("/health", headers={"X-Request-ID": bad_id})

    assert r.headers["X-Request-ID"] != bad_id
    assert re.fullmatch(r"[0-9a-f]{32}", r.headers["X-Request-ID"])


async def test_access_line_has_method_path_status_and_duration(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="app.access"):
        await client.get("/health")

    (record,) = [r for r in caplog.records if r.name == "app.access"]
    assert (record.method, record.path, record.status) == ("GET", "/health", 200)
    assert isinstance(record.duration_ms, float)
    assert record.getMessage() == "GET /health 200"


async def test_request_id_is_reset_after_the_request(client: AsyncClient) -> None:
    await client.get("/health")

    assert request_id_var.get() is None


async def test_unhandled_error_still_logs_status_500(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("boom")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    with caplog.at_level(logging.INFO, logger="app.access"):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/boom")

    assert r.status_code == 500
    (record,) = [r for r in caplog.records if r.name == "app.access"]
    assert record.status == 500
    assert request_id_var.get() is None
