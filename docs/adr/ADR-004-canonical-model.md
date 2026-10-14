# ADR-004: Canonical internal payment model

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

Bank inputs arrive as XML/JSON/CSV/API calls with vendor-specific structure. Downstream
validation, matching, and repair need one stable representation they can rely on.

## Decision

Define a **canonical internal payment model** in `packages/payment_domain`. Every inbound
payload is mapped onto this model (ADR over `mapping_engine`). The model is:
- deterministic and schema-validated (Pydantic v2),
- immutable for received evidence (ADR-006),
- redacted in repr/log output for financial/identity fields.

## Consequences

- Downstream engines depend on one model, not many vendor formats.
- Mapping is explicit; format-specific quirks are isolated.
- Adding a new source format requires a new mapping, not schema changes.
