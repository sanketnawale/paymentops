# Demo Script (30–40 minutes)

Audience: bank/fintech validation, operations, and architecture stakeholders.
Environment: `https://paymentops-dev.cloudnova.tech` (demo tenant `cloudnova-demo-bank`).
Credentials are provisioned out-of-band. PaymentOps is **non-transactional** — say this up front.

## 0. Framing (2 min)

"PaymentOps sits **beside** your payment stack. It validates, repairs, correlates, and reconciles
ISO 20022 message data and helps operators resolve exceptions. It never initiates or executes a
payment, and it never makes an authoritative decision — deterministic rules do, with a human in
the loop. AI, when enabled, only proposes candidates and explanations."

## 1. Sign in and role model (3 min)

1. Sign in as `demo-admin@cloudnova.tech`.
2. Show the dashboard: cases by state, readiness, recent activity.
3. Open **Settings**: point out the release/version/build metadata (`/api/v1/info`) and that
   zero-retention is on.

Optional: sign in as `demo-viewer@cloudnova.tech` and show that mutating actions are rejected
(server-side RBAC), then as `demo-operator@cloudnova.tech` to show operator actions succeed but
administrative configuration is denied.

## 2. Validation and deterministic repair (8 min)

1. Open **Validation & Repair**. Show a valid `pacs.008.001.08` (ready) and a message with address
   data that needs structuring (repairable/review).
2. Explain: schema validation is deterministic; repair produces a **candidate diff** and a
   re-validation result. Nothing is auto-applied — the operator approves.
3. Point out the schema-provenance note: bundled XSDs are CloudNova-authored subset schemas using
   real ISO namespaces, not official ISO packs.

## 3. Lifecycle correlation (6 min)

1. Show a `pain.001` initiation, its `pacs.008`, and the `pacs.002` status report forming a single
   lifecycle with the current status updated.
2. Show an out-of-order `pacs.002` (status arrives before the payment): it is held as `UNRESOLVED`
   and resolves when the parent arrives.

## 4. Account reconciliation (8 min)

1. Show a `camt.054` debit entry reconciled against a lifecycle, and a `camt.053` statement
   confirming the same event.
2. Show duplicate detection (same entry identity across two messages) and an amount mismatch that
   is deliberately **not** reconciled.
3. Explain the known limitation: a camt-first entry can remain `UNMATCHED_ACCOUNT_ENTRY`; automatic
   retroactive re-linking is not performed.

## 5. Exception operations (5 min)

1. Open a case routed to review (ambiguous/possible match). Show evidence, conflicts, and the
   human decision controls.
2. Emphasize: AI never approves or executes; it only proposes. The core product works with
   `AI_ENABLED=false`.

## 6. Security, tenancy, and operations (4 min)

- Tenant isolation: every query is organization-scoped; cross-tenant access is denied.
- Sessions are server-side and revocable; passwords are hashed with PBKDF2 (600k).
- Logs never contain payload data (IBANs, names, addresses, BICs) or secrets.
- Deployment is GitOps with pinned image SHAs; no `latest` tags.

## 7. Close (2 min)

- Recap: validate → repair → correlate → reconcile → resolve, all non-transactional and
  human-approved.
- Next step: agree PoC scope (message versions, sample payloads, success metrics) and an
  integration profile for your format variations.

## Reset between demos

```bash
kubectl -n paymentops exec deploy/paymentops-api -- \
  python -m scripts.reset_demo --org cloudnova-demo-bank --yes
kubectl -n paymentops exec deploy/paymentops-api -- \
  python -m scripts.seed_demo --org cloudnova-demo-bank
```
