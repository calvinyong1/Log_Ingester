# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# uv: fast Python package manager. Pulled from its official distroless image.
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first so the layer caches across code changes.
# Runtime deps only: pytest/ruff aren't shipped. Every `uv sync`/`uv run` here
# needs --no-dev (the UV_NO_DEV env var is did not apply to `uv run` in 0.5.4),
# or `uv run` would reinstall the dev group at container start.
COPY pyproject.toml ./
RUN uv sync --no-install-project --no-dev

# Copy app source.
COPY . .

# Resolve the project itself (creates the editable install for `app`).
RUN uv sync --no-dev

# Run as non-root.
RUN useradd --system --uid 1000 --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Migrations are a separate one-shot step (`uv run --no-dev alembic upgrade head`),
# so scaling the API to several tasks can't race on schema changes.
CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
