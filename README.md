# CloudNova PaymentOps

CloudNova PaymentOps is a **non-transactional payment-data intelligence platform**. It
ingests bank XML / JSON / CSV / API payloads, maps them to a canonical internal model, and
performs deterministic ISO 20022 validation, bank-specific rules, address intelligence,
fuzzy/entity analysis, optional (non-authoritative) AI explanation, candidate repair, and
human review — producing corrected output, reports, and an auditable trail.

## What PaymentOps is

- A payment **data intelligence** and **analytics/repair** platform.
- Deterministic validation with a canonical internal payment model.
- Designed for human-in-the-loop review and auditable correction.
- Able to run with generative AI **completely disabled**.

## What PaymentOps is **not**

- It does **not** initiate, authorize, send, or settle payments.
- It does **not** connect directly to settlement systems or release SWIFT messages.
- It does **not** make sanctions/AML clearance decisions.
- It is not a transaction execution or payments-rail system.

> PaymentOps is non-transactional. It does not execute or authorize payments.

## Hackathon build: AI investigation + Batch Exception Desk

> Demo and submission guide: **`docs/DEMO_RUNBOOK.md`**. This build is a hackathon submission;
> it is **not** production-certified.

### Problem and demonstrated solution

Payment exceptions (malformed or incomplete ISO 20022 payment instructions) are expensive to
triage by hand: an operator must find the real validation defect, work out which field is
missing, decide whether a defensible correction exists, and prove that correction does not
introduce new errors. The hackathon build demonstrates an end-to-end, evidence-backed loop:

1. **Deterministic first** - the real PaymentOps engine parses, XSD-validates, maps to the
   canonical model, runs versioned rules, and computes address readiness. This is authoritative.
2. **AI investigation** - an Evolus workflow (the **PaymentOps Investigator** agent, running on
   an **AMD Token Factory** model) consults a PaymentOps knowledge library and calls an
   authenticated PaymentOps validation tool, then explains the findings and proposes a repair.
3. **Evidence-backed repair** - the agent may only propose values that come from a synthetic
   supporting-evidence record; the server re-validates every proposal against allowlisted
   targets.
4. **Sandbox proof** - accepted changes are applied to a **copy** of the payload and re-validated
   by the same deterministic engine; the original is never modified.
5. **Bounded batch** - the **Batch Exception Desk** runs up to five cases through the same
   pipeline, sequentially, with per-item progress, sandbox testing and a review export.

### Exact roles of PaymentOps, Evolus and AMD Token Factory

| Component | Role in this demo |
| --- | --- |
| **CloudNova PaymentOps** | The deterministic payment-data intelligence platform and operator UI: ISO 20022 parsing/XSD validation, canonical model, versioned rules, address readiness, the server-side authenticated validation tool, evidence/allowlist checks, and sandbox re-validation. It is non-transactional and never executes or settles payments. |
| **Evolus** | The agent workflow/orchestration platform. The PaymentOps backend starts one investigation workflow, polls it, and ingests its structured result. The Evolus **PaymentOps Investigator** agent consults the `PaymentOps Rules` knowledge library and calls the PaymentOps validation tool. |
| **AMD Token Factory** | The model/inference and token budget behind the Evolus investigator agent (the demo model is served via AMD). PaymentOps does not call the model directly; it orchestrates the Evolus workflow. |

The deterministic engine is always authoritative; the agent only interprets and proposes.

### Demo instructions

- **Single-file journey** - open `/investigations`, upload one synthetic `pacs.008.001.08` XML
  (optionally with a per-case supporting-evidence JSON), watch the deterministic findings, start
  the Evolus investigation, read the investigator report, then use **Test proposed repair** to
  re-validate a sandbox copy. Sample bundles are downloadable on that page.
- **Batch Exception Desk** - open `/batches/exceptions`, add up to five rows (XML required,
  evidence JSON optional **per row**), submit, and watch per-item progress. Use **Test supported
  repairs** to sandbox-test a completed item and **Review export** for the JSON report.

Step-by-step recording instructions, verified case IDs and their expected outcomes are in
`docs/DEMO_RUNBOOK.md`.

### Local setup and required services

Required for the hackathon journey: **PostgreSQL** (investigations, batch records) and, for the
AI investigation step, a reachable **Evolus** workspace + AMD-backed model. Redis and the Celery
worker are only used by the **legacy** CSV batch module and are not required for the AI
investigation or Batch Exception Desk.

```powershell
# Backend (Python 3.12+)
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env         # secret-free placeholders only; never commit .env
docker compose up -d postgres  # PostgreSQL 16 on localhost:5432
alembic -c apps/api/alembic.ini upgrade head
uvicorn paymentops_api.main:app --host 0.0.0.0 --port 8000

# Frontend (Node 22+ / pnpm)
cd apps/web
pnpm install
pnpm dev                       # http://localhost:3000
```

Configuration is environment-only; see `.env.example` for the full, **secret-free** list
(placeholder values, including the Evolus identifiers and API keys). With `EVOLUS_ENABLED=false`
the platform still runs: the deterministic engine, repair proposals and sandbox testing work, and
the agent step reports a visible integration failure instead of a result.

### Existing foundation vs new hackathon contribution

- **Existing foundation (weeks 1-3, `v0.1.0-eval`)** - deterministic ISO 20022 engine, canonical
  payment model, versioned rules, address intelligence, integration profiles, matching/
  reconciliation, account reporting, cases, audit and payment lifecycles.
- **New hackathon contribution** - the Evolus/AMD investigator (Phase 1), the uploaded synthetic
  case journey with evidence-backed sandbox repair (Phase 2), consistent evidence-gap reporting
  and the bounded **Batch Exception Desk** with a durable background runner (Phase 3A).

### Supported scope and limitations

- **Single-transaction `pacs.008.001.08` only**; synthetic payloads only. No ZIP upload, no
  multi-transaction messages.
- Repairs require **matching supporting evidence**; unsupported or unevidenced changes are
  rejected. The sandbox proves only that the selected deterministic checks pass - it is **not**
  payment authorization, settlement readiness, or proof of payment safety.
- One model investigation runs at a time (shared Evolus/AMD key). The batch runner is an
  in-process, DB-backed task in a single API replica; it is durable across restarts but not
  horizontally scaled.
- The agent's narrative is non-authoritative; when its final answer cannot be cleanly separated
  from inline reasoning, the raw output is kept in a collapsed diagnostics panel and the
  structured findings/proposals are shown instead. Historical agent output is never rewritten.
- **No MCP integration, no second agent, and no production certification** are claimed.

### Batch runner architecture and ambiguous-start recovery

The Batch Exception Desk is a thin, tenant-scoped wrapper around the single-file pipeline. Work
is advanced by a **durable runner inside the API process** (started in the app lifespan), not by
browser polling and not by fire-and-forget request tasks - so a page refresh or a closed tab never
affects progress. State lives in PostgreSQL (`batch_runs`, `batch_items`); the runner claims one
item at a time via a `claimed_until` column and processes model investigations **sequentially**
(to respect the shared Evolus/AMD key). Each item persists its investigation/execution IDs,
progress and error.

Duplicate submissions are prevented by an organization-scoped `idempotency_key`. Duplicate
workflow starts are prevented by a **`STARTING` marker committed before the external call**; if
the process restarts mid-start, `recover_interrupted_starts()` marks the item failed as
*ambiguous* rather than starting a second external run. Rate limits respect `Retry-After` with
bounded backoff; batch progress is always distinct from sandbox outcome and human approval.

### No payment execution

Every input in this demo is synthetic. PaymentOps does not initiate, authorize, send, settle,
debit or credit payments; it does not connect to settlement systems; and the sandbox never
touches the original payload.

### Licences and third-party notices

This repository is proprietary (`license = { text = "Proprietary" }`). Third-party components and
attribution are retained in **`THIRD_PARTY.md`** (including the vendored Swift hybrid postal
address structuring component and its `third_party/swift-address/LICENSE.txt`). No third-party
notices were removed by the hackathon work.

## Evaluation release (`v0.1.0-eval`)

This repository is at the **v1 Evaluation Release**, intended for controlled bank/fintech
proof-of-concept engagements (not general availability).

- Release notes: `docs/RELEASE_NOTES.md`
- Release report & recommendation: `docs/release-report-v0.1.0-eval.md`
- Operations runbook: `docs/runbooks/operations.md`
- Demo script: `docs/demo-script.md`
- PoC package & security questionnaire: `docs/poc-package.md`
- Performance baseline: `docs/performance-baseline.md`
- Authentication & sessions: `docs/authentication.md`

The live build reports its `version`, `build_sha`, and `build_date` at `GET /api/v1/info`.

## Architecture

The application is a **modular monolith** (ADR-001). Components are separated into
installable Python packages and app entrypoints rather than microservices:

```
apps/api      FastAPI HTTP API (ASGI, uvicorn)
apps/web      Next.js + TypeScript frontend
apps/worker   Celery + Redis background worker
packages/     Shared, reusable domain + engine boundaries
```

`packages/` contains the canonical payment model (`payment_domain`) and the boundaries for
later engines (`iso_engine`, `rules_engine`, `address_engine`, `mapping_engine`,
`matching_engine`, `ai_gateway`, `masking`, `audit`). See `docs/architecture/overview.md`
for detail. Architectural decision records live in `docs/adr/`.

## Local development

Backend (Python 3.12+):

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
# copy local config
copy .env.example .env
# run the API
uvicorn paymentops_api.main:app --host 0.0.0.0 --port 8000
```

Frontend (Node 22+ / pnpm):

```powershell
cd apps/web
pnpm install
pnpm dev    # http://localhost:3000
```

Full stack via Docker Compose (PostgreSQL, Redis, API, worker, web):

```powershell
docker compose up --build
```

## Tests

Backend:

```powershell
pytest                     # unit + integration
ruff check . && ruff format --check .
mypy
```

Frontend:

```powershell
cd apps/web
pnpm lint
pnpm typecheck
pnpm build
```

## Environment variables

Configuration is read from the environment (and an optional `.env` in development). See
`.env.example`. **Never commit `.env` or real credentials.** All secrets are placeholders
there.

## Repository layout

```
apps/                api, web, worker
packages/            shared Python packages (payment_domain, iso_engine, rules_engine,
                     address_engine, repair_engine, analysis, mapping_engine, ...)
schemas/             bundled ISO 20022 subset schemas (schemas/iso20022/...)
rules/               reserved (configuration-driven bank rules)
tests/               unit, integration, security, regression, fixtures
docs/                adr, architecture, security
deploy/              deployment support
```

## Week 2: analysis vertical slice

The first complete production-quality slice is implemented:

- `POST /api/v1/payments/analyze` — secure pacs.008 XML ingestion, XSD validation, canonical
  mapping, deterministic rule findings, address readiness analysis, CloudNova address
  normalization, repair candidate generation, deterministic re-validation, structured diff,
  and hashes/audit metadata.
- Supported version: **`pacs.008.001.08`** (see `docs/adr/ADR-011`).
- Address providers: `CloudNovaAddressProvider` (default, deterministic) and the isolated
  `SwiftDerivedAddressProvider` (see `docs/adr/ADR-012` and `THIRD_PARTY.md`).
- Repair lifecycle: REPAIR_CANDIDATE -> VALIDATED_CANDIDATE (see `docs/adr/ADR-013`).
- Zero-retention by default: `persist=false` never stores raw XML.

Example:

```json
POST /api/v1/payments/analyze
{ "xml": "<pacs.008.../>", "repair": true, "persist": false }
```

See `docs/architecture/overview.md` for the full flow and `docs/security/security-principles.md`
for XML-security and zero-retention details.

## Week 3: multi-customer platform

Week 3 turns the engine into a configurable multi-customer payment-data platform:

- **Integration Profiles** — declarative, versioned mapping + rules per customer/input format
  (JSON, custom XML, CSV, ISO 20022 pacs.008). Published profiles are immutable; changes create
  a new draft version (see `docs/adr/ADR-015`).
- **Mapping engine** — controlled JSONPath/XPath/CSV selectors + a safe transform library into
  the canonical `PaymentMessage`. No arbitrary code execution.
- **Customer-specific rules** — declarative config rules over CloudNova baseline rules
  (baseline → org → profile hierarchy).
- **API client auth** — client_id + salted secret hash, org-scoped, maps to OAuth2/mTLS later.
- **Batch processing** — CSV upload → Celery/worker → aggregated readiness report (streaming,
  defensive limits).
- **Case/operator workflow** — human review with approve/reject/close. Approval approves the
  data-repair candidate only; it does not authorize or execute payments.
- **Tenant isolation** — every profile/version/case/batch/audit is scoped to `organization_id`.
- **Address coverage** — explicit `SUPPORTED` / `UNSUPPORTED_GEOGRAPHY` / `UNKNOWN` metadata
  (dev corpus covers IT/IN/SA/GB/DE/FR/ES/NL only).

Example:

```json
POST /api/v1/integration-profiles/<id>/publish
POST /api/v1/integrations/<profile_id>/analyze   (X-Client-Id / X-Client-Secret headers)
```

## Phase 1: Evolus integration & AMD-powered investigator

Phase 1 adds an **investigation-only** capability on top of the PaymentOps foundation
(non-transactional):

- **Deterministic first** — starting an investigation runs the real PaymentOps engine (secure
  parse, XSD validation, canonical mapping, versioned rules, address readiness).
- **Evolus workflow** — the backend starts a workflow whose **PaymentOps Investigator** agent
  (AMD Token Factory, Gemma-4-31B-IT) consults a knowledge library and calls an authenticated
  PaymentOps validation tool.
- **Narrow, authenticated tool** — `POST /api/v1/evolus/tools/validate-case` takes only a
  server-issued `case_ref` (no paths/URLs/tenant ids) and returns structured findings with real
  rule identifiers and field locations, clearly separated from agent interpretation.
- **UI** — `/investigations` starts a run from a synthetic demo case and shows progress,
  deterministic findings, the agent's explanation and cited rules, missing evidence, and the
  recommended human next step.
- **AI is optional** — with `EVOLUS_ENABLED=false` the platform works fully; the agent step
  reports a visible integration failure. The browser never receives API keys.

No repairs, payment execution or deployment are in scope; repair/revalidation and cluster
deployment are Phase 2.

- Phase 1 guide: `docs/PHASE1.md`
- Knowledge library: `docs/evolus/paymentops-rules-knowledge-base.md`
- Evolus workspace setup: `docs/evolus/evolus-workspace-setup.md`

## Kubernetes / GitOps deployment

Deployment targets a Kubernetes cluster managed by **Flux GitOps**, reusing the existing
CloudNova cluster conventions (Envoy Gateway routing, `base/` + `overlays/<env>` layout,
non-root hardened pods, explicit resources and probes). The GitOps overlay lives in the
**homeserver** repository under `clusters/loudnova/apps/paymentops/`. Logical environments:
`paymentops-dev`, `paymentops-test`, `paymentops-demo`. There is **no** `paymentops-prod`
yet. See `docs/architecture/overview.md` for the deployment model and current limitations.

## Week 1 limitations

Week 1 establishes the **foundation only**:

- No ISO/payment-processing logic, no pacs.008 parsing, no XSD validation, no address
  repair, no fuzzy reconciliation, no AI logic.
- Minimal database tables (`organizations`, `app_metadata`) — the real domain schema is
  designed and delivered in Week 2.
- Authentication is a placeholder (Keycloak / OIDC is planned).
- Single-node Kubernetes cluster: multiple replicas provide process-level HA, not
  infrastructure HA.
