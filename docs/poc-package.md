# PoC Package & Commercial Overview

This document is the starting point for a controlled bank/fintech proof-of-concept and for the
security review that precedes it. It intentionally avoids promising transaction-processing
capabilities: PaymentOps is **non-transactional**.

## 1. Product boundary

PaymentOps validates, repairs, correlates, and reconciles ISO 20022 payment **data**, and helps
operators resolve exceptions. It does **not** initiate, authorize, execute, or settle payments; it
does not perform sanctions/AML screening; and it never uses AI as an authoritative decision-maker.

## 2. PoC scope (proposed)

**In scope**

- ISO 20022 message versions: `pacs.008.001.08`, `pain.001.001.13`, `pacs.002.001.16`,
  `pacs.009.001.13`, `camt.053.001.14`, `camt.054.001.14`.
- Deterministic validation + repair-candidate workflow with human approval.
- Lifecycle correlation (pain/pacs.002, including out-of-order).
- Account reconciliation (camt.053/camt.054) with duplicate/amount-mismatch detection.
- Exception operations console with RBAC (ADMIN/OPERATOR/VIEWER).
- Tenant-isolated deployment for the customer.

**Out of scope**

- Any payment execution, authorization, settlement, or funds movement.
- Sanctions/AML, fraud scoring, or regulatory reporting.
- New ISO families or versions, and geography expansion.
- ML/LLM-based matching.

**Success criteria (agreed up front)**

- ≥ X% of submitted sample messages validate or produce an actionable repair candidate.
- Lifecycles correlate correctly for the agreed sample set (including out-of-order cases).
- Operators can resolve review cases with an auditable trail.
- All cross-tenant access attempts are denied.

## 3. Deployment options

- **CloudNova-hosted evaluation** (current): single-node K3s, Flux GitOps, Envoy Gateway +
  Cloudflare Tunnel, pinned image SHAs.
- **Customer-hosted**: container images deployed into the customer's Kubernetes; configuration via
  integration profiles (ADR-008), no per-customer code forks.

## 4. Security questionnaire (summary)

| Question | Answer |
| --- | --- |
| Does the product move money? | No. Non-transactional by design. |
| Is AI authoritative? | No. Deterministic validation is the only source of truth. Core works with AI disabled. |
| How are secrets handled? | Injected at runtime; `.env` gitignored; only `.env.example` committed. No secrets in images. |
| How are passwords stored? | PBKDF2-HMAC-SHA256, 600,000 iterations, per-user salt. |
| Session model? | Server-side opaque sessions (SHA-256 token hash), 8h TTL, revocable; lockout after 5 failures/15 min. |
| CSRF protection? | Double-submit cookie (`paymentops_csrf`) echoed via `X-CSRF-Token` on mutating requests. |
| Authorization? | Server-side RBAC in the web proxy: VIEWER/OPERATOR/ADMIN. |
| Tenant isolation? | Every organization-scoped query is tenant-scoped; cross-tenant access denied. |
| Logging of payload data? | Never. No IBANs, names, addresses, BICs, or raw payloads in logs. Masking utilities exist in `packages/masking`. |
| Payload immutability? | Received payloads are immutable evidence (ADR-006). |
| Encryption in transit? | TLS terminated at the edge (Cloudflare) and internal service traffic within the cluster. |
| Error responses? | Generic messages with a correlation id; no stack traces or config dumps. |
| Container security? | Non-root runtime; pinned image SHAs; no `latest` tags in production paths. |
| Debug mode in non-dev? | Disabled. |
| Data retention? | Zero-retention mode supported; raw payload TTL configurable. |
| Audit? | Authentication and operator actions recorded in `audit_events` (no secrets/payloads). |

## 5. Sales-engineering FAQ

**Q: Can it execute a payment?**
No. It is deliberately non-transactional. It prepares validated, reconciled data for your stack.

**Q: Does it use AI to match payments?**
No. Matching is deterministic (threshold-based). AI is optional and only proposes candidates or
explanations; it is never authoritative and can be disabled entirely.

**Q: Which ISO 20022 versions are supported?**
Exactly the six listed above. Unsupported versions return a structured error.

**Q: Are the XSDs official ISO packs?**
No. They are CloudNova-authored subset schemas using real ISO namespaces.

**Q: How do you handle customer-specific variations?**
Through declarative integration profiles (data, not code). No per-customer forks.

**Q: How is multi-tenancy enforced?**
Every query is organization-scoped and regression-tested for isolation.

**Q: How do we deploy?**
GitOps with pinned image digests, non-root containers, and no embedded secrets.

## 6. Commercial one-pager (positioning)

**CloudNova PaymentOps — payment-data intelligence, not payment execution.**

- **Problem:** payment operations teams lose time on format validation failures, repair loops,
  broken lifecycle correlation, and unreconciled account entries.
- **Solution:** a non-transactional control plane that validates, repairs, correlates, and
  reconciles ISO 20022 data, and gives operators a clean, auditable exception workflow.
- **Differentiators:** deterministic-first (no black-box decisions), human-in-the-loop, strong
  tenant isolation, configuration-over-fork, and an optional additive AI layer.
- **Deployment:** CloudNova-hosted evaluation or customer-hosted containers; GitOps, pinned SHAs.
- **Engagement:** time-boxed PoC against agreed sample payloads and success criteria.

## 7. Demo-request intake

The marketing site captures demo requests via `/api/demo-request`. Requests are delivered to a
configured `DEMO_REQUEST_WEBHOOK_URL`, or durably logged as structured `demo_request_received`
events (never silently discarded). Per-IP rate limiting (5/min) protects the endpoint.
