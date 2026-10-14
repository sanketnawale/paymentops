# ADR-008: Integration Profiles rather than per-customer forks

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

Banks have different formats, rules, and address conventions. Treating each customer's
behavior as bespoke code creates an unmaintainable fork-per-customer codebase.

## Decision

- **Customer-specific behavior is configuration-driven via integration profiles** (ADR-008).
- A profile is **data** (declarative configuration of mappings, rules, and addresses) — never
  executable code injected from customer input (rule #11).
- The codebase has no per-customer forks; behavior differences are profile-selected.

## Consequences

- One codebase serves all customers; onboarding adds a profile, not a fork.
- Profiles are versioned and auditable.
- Enforces a strict boundary: no arbitrary code execution through customer mappings.
