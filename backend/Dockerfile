FROM ghcr.io/astral-sh/uv:0.12.2 AS uv

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/backend/.venv/bin:$PATH"

WORKDIR /app/backend

COPY --from=uv /uv /uvx /bin/

# Install locked dependencies before copying the application so ordinary
# source edits do not invalidate the dependency layer.
# The backend installs the prediction package from ../ai, so both package
# manifests must exist before the locked environment can be restored.
COPY ai/pyproject.toml /app/ai/pyproject.toml
COPY ai/src /app/ai/src
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/src ./src
COPY backend/scripts ./scripts
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Migrations are the schema source of truth and must complete before the API
# starts accepting requests.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn wellness.main:app --host 0.0.0.0 --port 8000"]
