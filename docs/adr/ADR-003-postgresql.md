# ADR-003: PostgreSQL

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

Financial domain data needs a relational store with strong integrity, transactional
guarantees, JSON support, and rich indexing.

## Decision

Use **PostgreSQL** as the primary datastore. Access via SQLAlchemy 2 (async in the API,
sync for Alembic). Schema changes are managed by Alembic migrations (rule #12).

## Consequences

- Strong ACID guarantees and types (UUID, JSONB) relevant to payment data.
- Requires a running PostgreSQL for migrations/tests; migrations are validated offline.
- Redis remains the cache/queue layer, not the source of truth.
