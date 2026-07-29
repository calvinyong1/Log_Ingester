from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import logs
from app.config import get_settings


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

    return app


app = create_app()
