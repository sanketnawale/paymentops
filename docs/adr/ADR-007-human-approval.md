# ADR-007: Human approval for repair decisions

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

Automated repair can be wrong. Changes to validated financial data must not flow through
unchallenged.

## Decision

- **Human approval is required for repair decisions.** The platform produces corrected
  output, reports, and an audit trail for review.
- Automated engines (including AI) propose candidates; a human approves the final corrective
  action.
- Every correction must pass deterministic re-validation before being presented (this is a
  non-negotiable rule). AI is never the approver.

## Consequences

- Slower end-to-end flow, appropriate for correctness-critical payment data.
- Audit trail captures who approved what and why.
- Guards against automation error in financial context.
