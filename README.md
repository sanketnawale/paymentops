# CloudNova PaymentOps

CloudNova PaymentOps is an AI-assisted payment-message investigation platform. It applies
deterministic ISO 20022 validation to a payment message, has an Evolus investigator agent explain
the findings and propose a repair from a supporting-evidence record, verifies every proposal
server-side against allowlisted targets and evidence references, and proves the accepted changes
on a sandbox copy - while keeping a tenant-scoped, auditable record of the whole journey.

The platform investigates and repairs payment **data**. It does not initiate, authorize, send or
settle payments, and it does not connect to settlement systems.

## See it working

| Purpose | URL |
| --- | --- |
| Application | `https://paymentops-hackathon.cloudnova.tech` |
| Single-file investigations | `https://paymentops-hackathon.cloudnova.tech/investigations` |
| Batch Exception Desk | `https://paymentops-hackathon.cloudnova.tech/batches/exceptions` |
| Demo runbook (recording steps, verified cases, troubleshooting) | [`docs/DEMO_RUNBOOK.md`](docs/DEMO_RUNBOOK.md) |

Access is by workspace sign-in; credentials are injected at runtime from the deployment secret and
are not published anywhere in this repository. No video or slide links are published from this
repository.

## The operator workflow

1. **Upload** a synthetic `pacs.008.001.08` message, optionally with a supporting-evidence JSON.
2. **Validate** - the deterministic PaymentOps engine parses, XSD-validates, maps to the
   canonical model, runs versioned rules and computes address readiness. This is authoritative.
3. **Investigate** - the Evolus investigator agent reads the findings and proposes a repair drawn
   only from the supporting record.
4. **Check the evidence-linked proposals** - the server verifies each proposed target, party,
   value and `evidence_ref`; unsupported or unevidenced changes are rejected.
5. **Test a sandbox copy** - accepted changes are applied to a copy of the payload and
   re-validated by the same deterministic engine. The original is never modified.
6. **Review the remaining findings** - any finding that no evidence-backed change can resolve is
   surfaced as an unresolved finding or an explicit evidence gap.
7. **Export results** - download a tenant-scoped JSON review report.

**Investigation completion and sandbox validation are distinct.** A completed workflow means the
agent produced an investigation result; it does not mean a repair was validated. Sandbox
validation is a separate operator action with its own `VALIDATED` / `REVIEW_REQUIRED` outcome, and
neither state is human approval.

## Product capabilities

- Synthetic XML upload with an optional, explicitly paired supporting-evidence JSON.
- Deterministic PaymentOps validation: secure parse, XSD, canonical mapping, versioned rules and
  address-readiness analysis.
- Evolus investigator agent running on an **AMD Token Factory**-served **Gemma-4-31B-IT** model.
- Authenticated validation-tool calls from the workflow back into PaymentOps.
- Server-side checks over target, party, value and evidence reference before any change is kept.
- Sandbox-only repair with before/after findings; the original payload is immutable evidence.
- Explicit evidence gaps (supporting-record gaps, server-derived gaps and agent-reported gaps)
  and unresolved findings.
- Tenant-scoped dashboard, investigation records and a JSON review export.
- **Batch Exception Desk**: up to five items per batch, each with its own optional evidence.

## Demonstrated outcomes

The verified mixed batch **`bat-479164ac9021`** (synthetic demonstration data):

| Item | Input | Outcome |
| --- | --- | --- |
| 1 | Complete evidence | Two warnings -> zero: both towns repaired and sandbox-**VALIDATED** |
| 2 | Incomplete evidence | Debtor repair only; the creditor warning remains (sandbox **REVIEW_REQUIRED**) |
| 3 | Clean XML | No repair needed |
| 4 | Malformed XML | Rejected at upload; the other items continue |

These are synthetic demonstration results for one batch, not bank-wide accuracy or savings
metrics. Verified case IDs and their expected outcomes are listed in
[`docs/DEMO_RUNBOOK.md`](docs/DEMO_RUNBOOK.md).

## Architecture

- **Next.js / React frontend** - the operator UI and a same-origin, session-authenticated
  `/api/backend` proxy. The browser never holds API keys; the proxy injects the server-side
  operator credential and the trusted actor identity.
- **FastAPI API and the PaymentOps engine** - the deterministic ISO 20022 engine (parsing, XSD,
  canonical mapping, rules, address readiness), investigation records, evidence/allowlist checks,
  sandbox re-validation, the batch runner and the authenticated validation tool.
- **PostgreSQL** - tenant-scoped investigations, repair state, batch runs/items and sessions.
- **Evolus** - agent automation: the investigation workflow, the `PaymentOps Rules` knowledge
  library, and the validation WebAPI that calls back into PaymentOps.
- **Remote AMD Token Factory inference** - the model behind the Evolus investigator agent.

```mermaid
flowchart LR
  U["Operator browser"] -->|same-origin| W["Next.js UI + /api/backend proxy"]
  W -->|"X-Client-Id / X-Client-Secret"| A["FastAPI API + PaymentOps engine"]
  A <--> DB[("PostgreSQL")]
  A -->|"start workflow / poll"| E["Evolus automation"]
  E --> L["PaymentOps Rules library"]
  E -->|"validate-case (X-Tool-Key)"| A
  E --> M["AMD Token Factory model (Gemma-4-31B-IT)"]
  A -->|"sandbox re-validation"| A
```

## Deployment pipeline

```
GitHub (paymentops-amd) -> GitHub Actions -> GHCR ARM64 images -> Flux -> Hetzner K3s
```

- **GitHub Actions** builds and publishes `linux/arm64` API and web images to GHCR, tagged with
  the full commit SHA.
- **Flux** reconciles the cluster from the infra repository; image tags are pinned immutably in
  the overlay (no `latest`), and a one-shot migration Job applies Alembic migrations.
- **Hetzner K3s** runs the workloads in the isolated namespace `paymentops-hackathon`.
- **Cloudflare Tunnel** terminates public TLS/DNS and forwards to the in-cluster **Envoy Gateway**,
  which routes the hostname to the web service.

The hackathon deployment lives at
`clusters/hetzner-dr/apps/paymentops-hackathon/` in the infra repository (the `hetzner-dr`
cluster). This is distinct from other clusters and namespaces, which this build does not touch.

## Batch execution

The Batch Exception Desk reuses the single-file pipeline and is advanced by a **durable runner
inside the API process**, started with the application:

- **Persisted progress** - batch and item state lives in PostgreSQL, so a page refresh or a closed
  tab never changes progress and a restart resumes unfinished work.
- **Sequential items** - model investigations run one at a time so a batch does not fan out
  concurrent calls onto the shared Evolus/AMD key. This serializes a batch's own items; it is not
  a global lock over every request in the platform.
- **Organization-scoped idempotency** - a batch submission carries an idempotency key; a repeat
  returns the existing batch instead of starting new work.
- **Ambiguous-start recovery** - a `STARTING` marker is committed before the external workflow
  call. If the process restarts mid-start, the item is marked failed as *ambiguous* rather than
  blindly resubmitted, so a duplicate external run is never started.

The runner is intentionally single-process (one API replica) in this deployment; it is durable
across restarts but is not horizontally scaled.

## Quick start and configuration

Requirements: Python 3.12+, Node 22+ with pnpm, and Docker (for a local PostgreSQL). All commands
are one coherent path from a fresh clone.

```powershell
# 1. Backend dependencies and local config
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env            # placeholder values only; never commit .env

# 2. PostgreSQL (required) - Redis is NOT required for the investigation/Batch Exception Desk
docker compose up -d postgres

# 3. Database schema (run Alembic from the API package, where alembic.ini lives)
cd apps\api
alembic upgrade head

# 4. Seed the demo tenant + operator API client (idempotent; run from apps\api)
python -m scripts.seed_hackathon
cd ..\..

# 5. API (http://localhost:8000)
uvicorn paymentops_api.main:app --host 0.0.0.0 --port 8000

# 6. Web (http://localhost:3000)
cd apps\web
pnpm install
pnpm dev
```

The web proxy reads `PAYMENTOPS_INTERNAL_API_URL` (default `http://localhost:8000`),
`PAYMENTOPS_CLIENT_ID`, `PAYMENTOPS_CLIENT_SECRET` and `PAYMENTOPS_OPERATOR_ORG_ID` from the
server environment - use the operator client created by the seed step. Configure these in a local
`.env`/server environment; **secrets never belong in browser code**.

**Optional services.** Redis and the Celery worker are only used by the legacy CSV batch module
(`/api/v1/batches`); neither is required for the investigation journey or the Batch Exception
Desk.

**What works without Evolus.** With `EVOLUS_ENABLED=false` (or missing Evolus credentials) the
platform still runs end to end for deterministic validation, evidence/allowlist checks and sandbox
re-validation - but the AI investigation step cannot run: the investigation is reported as an
integration failure instead of producing an agent result. The AI journey requires a configured
Evolus workspace and model access. Evolus identifiers and keys are configured server-side only
(see `.env.example`).

## API overview

Operator routes are authenticated (workspace session via the `/api/backend` proxy); generation
still requires org-scoped credentials. Paths below are relative to the API root.

| Method and path | Purpose | Auth |
| --- | --- | --- |
| `POST /api/v1/investigations/upload` | Create an investigation from an uploaded synthetic XML (+ optional evidence) | Operator |
| `GET /api/v1/investigations` | List the tenant's investigations | Operator |
| `GET /api/v1/investigations/{investigation_id}` | Investigation detail (deterministic findings, agent result, evidence gaps, repair) | Operator |
| `POST /api/v1/investigations/{investigation_id}/repair/test` | Test the supported proposals on a sandbox copy | Operator |
| `POST /api/v1/exception-batches` | Submit a batch of up to five explicitly paired items | Operator |
| `GET /api/v1/exception-batches` | List the tenant's batches | Operator |
| `GET /api/v1/exception-batches/{batch_id}` | Per-item progress, findings and sandbox state | Operator |
| `POST /api/v1/exception-batches/{batch_id}/items/{item_id}/repair/test` | Sandbox-test one item | Operator |
| `GET /api/v1/exception-batches/{batch_id}/export` | Tenant-authorized JSON review report | Operator |
| `POST /api/v1/evolus/tools/validate-case` | Structured validation for the Evolus workflow (body: `{"case_ref": "<server-issued>"}`) | Tool credential (`X-Tool-Key`) |
| `GET /health`, `GET /ready`, `GET /metrics`, `GET /api/v1/info` | Liveness, readiness, metrics, build metadata | Internal / probe |

The validation tool is called by the Evolus workflow, not by the browser, and accepts only a
server-issued `case_ref`. Replace every credential/identifier placeholder with your own values.

## Verification

Run from the repository root unless noted.

```powershell
# Backend (PostgreSQL required for the integration/security suites)
docker compose up -d postgres
$env:TEST_DATABASE_URL = "postgresql+asyncpg://paymentops:localdev-only@localhost:5432/paymentops"
pytest
ruff check .
ruff format --check .
mypy apps/api/paymentops_api

# Frontend
cd apps\web
pnpm typecheck      # tsc --noEmit
pnpm lint           # next lint
pnpm test           # vitest run
pnpm build          # next build
```

Current state of this release (local, PostgreSQL 16): the backend suite passes **318 tests**, and
the frontend passes **44 Vitest tests** with clean `tsc --noEmit`, `next lint` and `next build`.
The tests cover the upload journey, evidence-gap reporting, batch validation/isolation,
idempotency, restart recovery, export semantics and the UI status mapping. The deployed image
versions, migration head and verified live case IDs are recorded in
[`docs/DEMO_RUNBOOK.md`](docs/DEMO_RUNBOOK.md). See also
[`docs/PHASE2_DEPLOY.md`](docs/PHASE2_DEPLOY.md) for the deployment walkthrough.

## Supported inputs and operating boundaries

- **Synthetic data only.** Uploads are synthetic; treat every payload as untrusted input.
- **Message coverage:** single-transaction `pacs.008.001.08` only. No ZIP upload and no
  multi-transaction messages.
- **Upload limits:** XML up to **256 KiB** (`262144` bytes) and evidence JSON up to **64 KiB**
  (`65536` bytes); a batch holds at most **five** items.
- **Supported repair targets:** address town/country limited to
  `(Dbtr|Cdtr|DbtrAgt|CdtrAgt)/PstlAdr/(TwnNm|Ctry)`, and only when a matching evidence reference
  is present and its value matches.
- **Sandbox scope:** a sandbox pass means the selected, configured deterministic checks were
  re-evaluated cleanly on a copy of the message. It is not a statement about the whole payment and
  is not a guarantee of safety.

PaymentOps investigates payment data. It does not move funds.

## Documentation and licensing

- Demo runbook: [`docs/DEMO_RUNBOOK.md`](docs/DEMO_RUNBOOK.md)
- Upload journey and evidence schema: [`docs/PHASE2C_UPLOAD.md`](docs/PHASE2C_UPLOAD.md)
- Sandbox repair and validation: [`docs/PHASE2B_REPAIR.md`](docs/PHASE2B_REPAIR.md)
- UI and API surface: [`docs/PHASE2D_UI_AND_API.md`](docs/PHASE2D_UI_AND_API.md)
- Evolus workspace setup: [`docs/evolus/evolus-workspace-setup.md`](docs/evolus/evolus-workspace-setup.md)
- Rules knowledge library: [`docs/evolus/paymentops-rules-knowledge-base.md`](docs/evolus/paymentops-rules-knowledge-base.md)
- Deployment walkthrough: [`docs/PHASE2_DEPLOY.md`](docs/PHASE2_DEPLOY.md)

This project's own metadata declares the license as **Proprietary** (`pyproject.toml`,
`license = { text = "Proprietary" }`); there is no top-level `LICENSE` file in the repository. No
organizer or competition-terms document is present in the repository to confirm how the entry may
be licensed or distributed, so that question is left to the project owners and the organizers.

Third-party components and attribution are recorded in [`THIRD_PARTY.md`](THIRD_PARTY.md),
including the vendored Swift hybrid postal-address structuring component
(`third_party/swift-address/LICENSE.txt` and `third_party/swift-address-resources/LICENSE.txt`).
Those notices and licences are preserved unchanged; this project does not relicense third-party
code.
