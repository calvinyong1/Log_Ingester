from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/logs"
    redis_url: str = "redis://redis:6379/0"
    env: str = "development"
    log_level: str = "INFO"

    # Comma-separated list of origins allowed to hit the API from a browser,
    # e.g. "http://localhost:5173,http://localhost:3000"
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    # Rolling per-service error-rate window used by the worker
    error_rate_window_seconds: int = 300
    error_rate_threshold: float = 0.5
    error_rate_min_events: int = 5
    alert_cooldown_seconds: int = 300
    alert_webhook_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
