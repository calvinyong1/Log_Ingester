import redis
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import logs
from app.config import get_settings
from app.db import get_session
from app.queue import get_redis_connection


def create_app() -> FastAPI:
    app = FastAPI(
        title="Log Anomaly Detection",
        version="0.1.0",
        description="Ingest, store, and detect anomalies in application logs.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(logs.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", tags=["meta"])
    async def ready(
        session: AsyncSession = Depends(get_session),
        redis_conn: redis.Redis = Depends(get_redis_connection),
    ) -> dict[str, str]:
        # /health only says the process is up; this says it can do its job.
        try:
            await session.execute(text("SELECT 1"))
            redis_conn.ping()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Dependency unavailable",
            ) from exc
        return {"status": "ready"}

    return app


app = create_app()
