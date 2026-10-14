# ADR-010: Configurable zero-retention processing

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

Financial payloads are sensitive. Storing them longer than necessary increases exposure and
compliance burden.

## Decision

- **Zero-retention is the default posture** (`ZERO_RETENTION_ENABLED=true`).
- Raw payload retention is configurable (`RAW_PAYLOAD_TTL_SECONDS`); `0` means immediate
  non-retention after processing.
- When zero-retention is active, raw evidence is not persisted; derived/canonical output and
  the audit trail carry the information required.

## Consequences

- Reduced data exposure and a defensible data-minimization posture.
- Must reconcile with ADR-006 (immutable evidence): retention policy governs how long raw
  evidence is held, while what is held is never mutated.
- Configurable per environment so dev/test can retain for debugging while prod minimizes.
