import redis
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import alerts, logs, services
from app.config import get_settings
from app.db import get_session
from app.logging_config import configure_logging
from app.middleware import RequestContextMiddleware
from app.queue import get_redis_connection


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    app = FastAPI(
        title="Log Monitor",
        version="0.1.0",
        description="Ingest, store, and detect anomalies in application logs.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    # Added last so it is outermost and sees every request, preflights included.
    app.add_middleware(RequestContextMiddleware)
    app.include_router(logs.router)
    app.include_router(alerts.router)
    app.include_router(services.router)

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
