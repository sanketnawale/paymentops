# syntax=docker/dockerfile:1
# CloudNova PaymentOps - API image.
# Build context MUST be the repository root because the package is installed from it:
#   docker build -f apps/api/Dockerfile -t paymentops-api:dev .
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# Install build-fix deps (psycopg2 needs libpq and build tools).
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY packages ./packages
COPY apps/api ./apps/api
COPY apps/worker ./apps/worker
COPY schemas ./schemas

# Create an isolated venv and install the package (+ runtime deps only).
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Minimal runtime libs; libpq for psycopg2.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user.
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /srv/app

# Copy the app code (source needed for Alembic migrations), migrations, and bundled schemas.
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder --chown=appuser:appgroup /build/apps/api /srv/app
COPY --from=builder --chown=appuser:appgroup /build/schemas /srv/app/schemas

# Point the XSD validator at the bundled schemas inside the image.
ENV PAYMENTOPS_SCHEMA_DIR=/srv/app/schemas/iso20022

# Non-sensitive build metadata surfaced by /api/v1/info.
ARG BUILD_SHA=unknown
ARG BUILD_DATE=unknown
ENV BUILD_SHA=$BUILD_SHA \
    BUILD_DATE=$BUILD_DATE

USER appuser

EXPOSE 8000

# Default: fail prompt is avoided; use --preload for reliable signal handling.
CMD ["sh", "-c", "alembic upgrade head && uvicorn paymentops_api.main:app --host 0.0.0.0 --port 8000"]
