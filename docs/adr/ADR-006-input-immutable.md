# ADR-006: Original input is immutable

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

Payment payloads are evidence. If repair, mapping, or validation mutates the original data,
reproduction and audit are impossible.

## Decision

- **Original financial payloads are immutable evidence.** Never mutate a received payload.
- Store original input read-only where applicable; record the canonical model derived from it.
- Corrections are applied to a separate candidate/corrected representation, never to the
  original.

## Consequences

- Clear provenance chain: original evidence → canonical model → candidate repair → verified.
- Auditable and reproducible validation results.
- Requires storage strategy that separates evidence from derived data.
