# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# uv: fast Python package manager. Pulled from its official distroless image.
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first so the layer caches across code changes.
# Dev deps are included so `pytest` can run inside the container; for a real
# production image, swap to `--no-dev` and add a separate `test` build target.
COPY pyproject.toml ./
RUN uv sync --no-install-project

# Copy app source.
COPY . .

# Resolve the project itself (creates the editable install for `app`).
RUN uv sync

# Run as non-root.
RUN useradd --system --uid 1000 --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Apply migrations, then start uvicorn. Compose overrides this only if needed.
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
