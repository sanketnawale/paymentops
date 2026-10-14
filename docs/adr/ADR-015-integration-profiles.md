# ADR-015: Integration Profiles and multi-customer configuration

- **Status:** Accepted
- **Date:** 2026-09-05

## Context

Week 2 built a customer-independent engine. Week 3 makes it a configurable multi-customer
platform. Different banks send different formats; customer-specific behavior must be
configuration-driven, not codebase forks (ADR-008).

## Decision

- **Integration Profiles** are first-class, versioned, immutable-when-published. A published
  profile snapshots its mapping + ruleset; changes create a new draft version.
- **Mapping engine** maps customer input (JSON / custom XML / CSV / pacs.008) into the
  canonical `PaymentMessage` via declarative field mappings with controlled selectors
  (JSONPath-like, XPath-like, CSV columns) and a safe, versioned transform library. No
  arbitrary code execution.
- **Rules** use a hierarchy: CloudNova baseline → organization overlay → profile overlay.
  Customers configure declarative rules with an allowlisted operator set; they cannot disable
  system/structural validation.
- **Tenant isolation** is enforced at the DB/service layer: every profile, version, case,
  batch job, and audit record carries `organization_id`.
- **API client auth** is a client_id + salted secret hash, org-scoped, mapped to OAuth2 client
  credentials / mTLS later. Secrets are never stored in plaintext.
- **Batch** uses the existing Celery/Redis worker with streaming and defensive limits.
- **Address coverage** is explicit (`SUPPORTED` / `UNSUPPORTED_GEOGRAPHY` / `UNKNOWN`); the
  development corpus covers IT/IN/SA/GB/DE/FR/ES/NL and is not presented as global.

## Consequences

- New bank onboarding = a new profile, not a fork.
- Version compatibility is recorded per analysis (profile/mapping/ruleset/provider/engine).
- Operator review approves a **data-repair candidate only** — never a payment action.
- Zero-retention posture retained: raw payloads are never stored by default.
