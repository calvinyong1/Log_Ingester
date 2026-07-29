import redis
from rq import Queue

from app.config import get_settings

QUEUE_NAME = "ingest"

_redis_conn: redis.Redis | None = None


def get_redis_connection() -> redis.Redis:
    global _redis_conn
    if _redis_conn is None:
        _redis_conn = redis.from_url(get_settings().redis_url)
    return _redis_conn


def get_queue() -> Queue:
    return Queue(QUEUE_NAME, connection=get_redis_connection())
