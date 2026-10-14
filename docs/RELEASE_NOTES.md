# Release Notes — v1 Evaluation Release (`v0.1.0-eval`)

**Product:** CloudNova PaymentOps
**Version:** `0.1.0-eval`
**Environment:** development / demo (controlled PoC)
**Nature:** NON-TRANSACTIONAL payment-data intelligence. PaymentOps never initiates, approves,
executes, or settles payments.

This is an **evaluation release** intended for controlled bank/fintech proof-of-concept
engagement. It is not a general-availability or production release.

## Highlights

- **ISO 20022 validation & repair** for six exact message versions:
  `pacs.008.001.08`, `pain.001.001.13`, `pacs.002.001.16`, `pacs.009.001.13`,
  `camt.053.001.14`, `camt.054.001.14`.
- **Deterministic validation and repair** with human-in-the-loop review. AI is optional,
  additive, and never authoritative (`AI_ENABLED=false` is fully supported).
- **Payment lifecycle correlation** across pain/pacs.002 with out-of-order resolution.
- **Account reconciliation** from camt.053/camt.054 with duplicate and amount-mismatch detection.
- **Operator console** (Next.js) with server-side sessions, RBAC, CSRF protection, and a
  same-origin backend proxy.
- **Tenant isolation** enforced across every organization-scoped resource.
- **GitOps deployment** (Flux) to a single-node K3s cluster; Envoy Gateway + Cloudflare Tunnel.

## What's new in this release

- Application authentication: local users, PBKDF2-HMAC-SHA256 (600k iterations), server-side
  revocable sessions (8h TTL), lockout after 5 failures / 15 minutes.
- Role-based authorization in the web proxy: VIEWER (read-only), OPERATOR (case/match/reconciliation
  actions), ADMIN (integration-profile and client configuration).
- Authentication audit events (`auth.login`, `auth.logout`).
- User administration CLI (`scripts.user_admin`).
- Demo tenant tooling (`scripts.seed_demo`, `scripts.reset_demo`).
- Build metadata surfaced by `/api/v1/info` (`release`, `version`, `build_sha`, `build_date`).
- CI now runs a real PostgreSQL service and executes the integration/security DB suites.

## Non-goals (out of scope by design)

Payment execution/authorization/settlement, debit/credit movements, sanctions/AML screening,
ML/LLM-based matching, Kafka/IBM MQ, ISO families beyond the six listed, and geography expansion.

## Known limitations

- The backend authenticates a single operator client; per-user authorization is enforced in the
  web proxy. The backend cannot distinguish end users (documented limitation).
- Bundled XSDs are CloudNova-authored **subset** schemas using real ISO namespaces, not official
  ISO schema packs.
- Large-statement (`camt.053`) ingest is bounded; asynchronous large-statement processing is not
  fully wired.
- camt-first entries may remain `UNMATCHED_ACCOUNT_ENTRY`; automatic retroactive re-linking is not
  performed.
- One operator tenant per deployment.

## Verification summary

- Backend: `ruff`, `ruff format --check`, `mypy`, and `pytest` (unit + integration + security)
  all pass; the DB suites run against PostgreSQL.
- Frontend: ESLint, `tsc --noEmit`, Vitest, and `next build` all pass.
- Live dev environment verified: anonymous redirect to `/login`, authenticated dashboard, RBAC
  denials (operator→admin 403, viewer→mutating 403), session logout, tenant guard 403.
- Backup/restore verified by dumping the database and restoring into an isolated database with
  matching row counts and migration head.

## Evaluation entry points

- App: `https://paymentops-dev.cloudnova.tech`
- Demo users: `demo-admin@cloudnova.tech`, `demo-operator@cloudnova.tech`,
  `demo-viewer@cloudnova.tech` (credentials provisioned out-of-band; never committed).
- Demo tenant: `cloudnova-demo-bank`.
