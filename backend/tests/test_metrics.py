from unittest import mock

import fakeredis
import pytest
import redis
from httpx import AsyncClient
from prometheus_client.parser import text_string_to_metric_families
from rq import Queue
from rq.registry import FailedJobRegistry

from app.main import app
from app.metrics import INGESTED, QUEUE_WAIT_BUCKETS, record_queue_wait, render
from app.queue import get_redis_connection


@pytest.fixture
def redis_conn() -> fakeredis.FakeStrictRedis:
    return fakeredis.FakeStrictRedis()


def _samples(output: bytes) -> dict[tuple[str, tuple[tuple[str, str], ...]], float]:
    return {
        (sample.name, tuple(sorted(sample.labels.items()))): sample.value
        for family in text_string_to_metric_families(output.decode())
        for sample in family.samples
    }


def _value(output: bytes, name: str, **labels: str) -> float:
    return _samples(output)[(name, tuple(sorted(labels.items())))]


def test_queue_depth_counts_waiting_jobs(redis_conn) -> None:
    queue = Queue("ingest", connection=redis_conn)
    for _ in range(3):
        queue.enqueue("app.worker.tasks.process_log_event", {})

    assert _value(render(redis_conn), "ingest_queue_depth") == 3


def test_failed_jobs_counts_the_failed_registry(redis_conn) -> None:
    registry = FailedJobRegistry(queue=Queue("ingest", connection=redis_conn))
    # A far-future score so RQ's cleanup treats the entry as unexpired.
    redis_conn.zadd(registry.key, {"some-job-id": 4_000_000_000})

    assert _value(render(redis_conn), "ingest_failed_jobs") == 1


def test_empty_queue_and_no_latency_data_render_valid_output(redis_conn) -> None:
    output = render(redis_conn)

    assert _value(output, "ingest_queue_depth") == 0
    assert _value(output, "ingest_failed_jobs") == 0
    assert _value(output, "ingest_queue_wait_seconds_count") == 0
    assert _value(output, "ingest_queue_wait_seconds_bucket", le="+Inf") == 0


def test_record_queue_wait_fills_buckets_sum_and_count(redis_conn) -> None:
    for seconds in (0.003, 0.02, 0.02, 0.3, 4):
        record_queue_wait(redis_conn, seconds)

    output = render(redis_conn)
    assert _value(output, "ingest_queue_wait_seconds_bucket", le="0.005") == 1
    assert _value(output, "ingest_queue_wait_seconds_bucket", le="0.025") == 3
    assert _value(output, "ingest_queue_wait_seconds_bucket", le="0.5") == 4
    assert _value(output, "ingest_queue_wait_seconds_bucket", le="5.0") == 5
    assert _value(output, "ingest_queue_wait_seconds_bucket", le="+Inf") == 5
    assert _value(output, "ingest_queue_wait_seconds_sum") == pytest.approx(4.343)
    assert _value(output, "ingest_queue_wait_seconds_count") == 5


def test_wait_above_the_last_bucket_lands_in_inf(redis_conn) -> None:
    record_queue_wait(redis_conn, 120)

    output = render(redis_conn)
    assert _value(output, "ingest_queue_wait_seconds_bucket", le="60.0") == 0
    assert _value(output, "ingest_queue_wait_seconds_bucket", le="+Inf") == 1


def test_negative_wait_is_clamped_to_zero(redis_conn) -> None:
    record_queue_wait(redis_conn, -1)

    output = render(redis_conn)
    assert _value(output, "ingest_queue_wait_seconds_bucket", le="0.005") == 1
    assert _value(output, "ingest_queue_wait_seconds_sum") == 0


def test_buckets_are_the_documented_ones() -> None:
    assert QUEUE_WAIT_BUCKETS == (
        0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60,
    )  # fmt: skip


def test_ingested_counter_renders_the_level_label(redis_conn) -> None:
    before = _samples(render(redis_conn)).get(
        ("log_events_ingested_total", (("level", "ERROR"),)), 0
    )

    INGESTED.labels(level="ERROR").inc()

    assert _value(render(redis_conn), "log_events_ingested_total", level="ERROR") == before + 1


async def test_metrics_endpoint_returns_prometheus_text(client: AsyncClient) -> None:
    app.dependency_overrides[get_redis_connection] = lambda: fakeredis.FakeStrictRedis()

    r = await client.get("/metrics")

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "ingest_queue_depth" in r.text


async def test_metrics_returns_503_when_redis_is_down(client: AsyncClient) -> None:
    broken = mock.MagicMock(spec=redis.Redis)
    broken.pipeline.side_effect = redis.ConnectionError("down")
    broken.hgetall.side_effect = redis.ConnectionError("down")
    broken.llen.side_effect = redis.ConnectionError("down")
    broken.zcard.side_effect = redis.ConnectionError("down")
    app.dependency_overrides[get_redis_connection] = lambda: broken

    r = await client.get("/metrics")

    assert r.status_code == 503


async def test_metrics_is_not_in_the_openapi_schema(client: AsyncClient) -> None:
    r = await client.get("/openapi.json")

    assert "/metrics" not in r.json()["paths"]
