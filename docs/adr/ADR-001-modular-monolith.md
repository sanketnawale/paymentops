# ADR-001: Modular monolith first

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

The platform spans mapping, ISO validation, rules, address intelligence, matching, optional
AI, repair, and human review. An early split into microservices would add operational
overhead (networking, tracing, deployment sprawl) before complexity is proven.

## Decision

Ship a **modular monolith**. Shared, cohesive logic lives in installable Python packages
(`packages/*`); command/query entrypoints are thin (`apps/api`, `apps/worker`). Module
boundaries are enforced by package imports, not network calls.

## Consequences

- Clean internal boundaries without distributed-systems cost.
- Easy to extract a service later if demonstrated need arises (requires a new ADR).
- Single deployable surface in Week 1.
