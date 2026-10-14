# ADR-002: Python + FastAPI backend

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

We need a backend with strong validation, async I/O, HTTP APIs, and easy testability.

## Decision

- **Language:** Python 3.12+ (typing, mature ecosystem).
- **Framework:** FastAPI.
- **Validation:** Pydantic v2.
- **Persistence:** SQLAlchemy 2 (async) + Alembic.
- **Tests:** pytest + httpx.

## Consequences

- Type-safe request/response models with OpenAPI generation.
- Single language across API and worker; shared code via packages.
- Mature ecosystem for XML/JSON/CSV, Celery, and PostgreSQL.
