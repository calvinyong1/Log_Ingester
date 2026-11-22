from collections.abc import Iterator

import redis
from prometheus_client import CollectorRegistry, Counter, disable_created_metrics, generate_latest
from prometheus_client.core import GaugeMetricFamily, HistogramMetricFamily
from prometheus_client.registry import Collector
from rq import Queue
from rq.registry import FailedJobRegistry

from app.queue import QUEUE_NAME

# Seconds a job may wait between enqueue and a worker starting it. Finer at the
# small end because most waits should be quick.
QUEUE_WAIT_BUCKETS: tuple[float, ...] = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60,
)  # fmt: skip

# The worker is a separate process, so its latency numbers can't live in this
# one's memory: it adds each wait to this Redis hash and the API turns it into a
# histogram on every scrape. Fields: str(bound) per finite bucket (counts are
# per-bucket here, cumulative in the output), "inf", "sum" and "count".
_WAIT_KEY = "metrics:queue_wait"
_INF_FIELD = "inf"

# The `_created` series would only add a second line per label for nothing to read.
disable_created_metrics()

# Per-process, so it resets when the API restarts; Prometheus's rate() copes
# with that. `level` is the only label: `service` is chosen by callers and would
# let the label set grow without bound.
_ingest_registry = CollectorRegistry()
INGESTED = Counter(
    "log_events_ingested",
    "Log events accepted by POST /logs (a 202 was returned).",
    ["level"],
    registry=_ingest_registry,
)


def record_queue_wait(redis_conn: redis.Redis, seconds: float) -> None:
    # Clock skew between hosts could give a negative wait; count it as zero so the
    # sum never goes down.
    seconds = max(seconds, 0.0)
    field = next((str(b) for b in QUEUE_WAIT_BUCKETS if seconds <= b), _INF_FIELD)
    pipe = redis_conn.pipeline()
    pipe.hincrby(_WAIT_KEY, field, 1)
    pipe.hincrbyfloat(_WAIT_KEY, "sum", seconds)
    pipe.hincrby(_WAIT_KEY, "count", 1)
    pipe.execute()


class PipelineCollector(Collector):
    """Reads queue state from Redis each time Prometheus scrapes."""

    def __init__(self, redis_conn: redis.Redis) -> None:
        self._redis = redis_conn

    def collect(self) -> Iterator[GaugeMetricFamily | HistogramMetricFamily]:
        queue = Queue(QUEUE_NAME, connection=self._redis)
        depth = GaugeMetricFamily("ingest_queue_depth", "Jobs waiting in the ingest queue.")
        depth.add_metric([], queue.count)
        yield depth

        failed = GaugeMetricFamily(
            "ingest_failed_jobs", "Jobs that used up their retries and failed."
        )
        failed.add_metric([], FailedJobRegistry(queue=queue).count)
        yield failed

        yield self._queue_wait()

    def _queue_wait(self) -> HistogramMetricFamily:
        raw = {
            (k.decode() if isinstance(k, bytes) else k): float(v)
            for k, v in self._redis.hgetall(_WAIT_KEY).items()
        }
        buckets: list[tuple[str, float]] = []
        running = 0.0
        for bound in QUEUE_WAIT_BUCKETS:
            running += raw.get(str(bound), 0.0)
            buckets.append((str(float(bound)), running))
        running += raw.get(_INF_FIELD, 0.0)
        buckets.append(("+Inf", running))

        histogram = HistogramMetricFamily(
            "ingest_queue_wait_seconds",
            "Seconds between a job being enqueued and a worker starting it.",
        )
        histogram.add_metric([], buckets, raw.get("sum", 0.0))
        return histogram


def render(redis_conn: redis.Redis) -> bytes:
    # A throwaway registry per call keeps the collector's Redis connection from
    # becoming shared state.
    pipeline_registry = CollectorRegistry()
    pipeline_registry.register(PipelineCollector(redis_conn))
    return generate_latest(_ingest_registry) + generate_latest(pipeline_registry)
