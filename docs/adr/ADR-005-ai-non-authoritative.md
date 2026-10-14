# ADR-005: AI is non-authoritative

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

Generative AI can produce fluent but incorrect results. Financial validation must never
depend on a stochastic model.

## Decision

- **Deterministic validation is the only source of truth.** AI is never authoritative.
- **AI never approves or executes financial actions.** It may propose candidates and
  explanations only.
- **The platform is fully usable with AI disabled** (`AI_ENABLED=false`).
- AI is accessed through a provider abstraction (`packages/ai_gateway`) supporting Ollama /
  vLLM / customer-approved providers.

## Consequences

- AI adds value (explanation, candidate generation) without control over outcomes.
- Every AI suggestion must pass deterministic re-validation before human review.
- No model-specific business logic in core paths.
