# CloudNova PaymentOps

AI-assisted payment-message investigation with evidence-backed corrections and sandbox verification.

PaymentOps investigates payment data. It does not move funds.

## 1. Try PaymentOps

- **Application:** https://paymentops-hackathon.cloudnova.tech
- **Investigations:** https://paymentops-hackathon.cloudnova.tech/investigations
- **Batch Exception Desk:** https://paymentops-hackathon.cloudnova.tech/batches/exceptions

Sign in with the workspace account to use the operator UI. Credentials are injected at runtime and
are never published in this repository.

## 2. The problem

Investigating an incomplete payment message is skilled manual work. An operator has to locate the
validation defect, work out which field is actually missing, search for evidence that supports a
value, and check that a proposed correction does not introduce new errors elsewhere. Doing this by
hand for a single message is slow, and doing it across a queue invites inconsistent decisions.

PaymentOps shortens that loop by combining deterministic validation with an investigator agent and
a server-checked, evidence-backed correction step - without ever touching the original message.

## 3. How it works

**Upload -> validate -> investigate -> evidence-backed proposal -> sandbox test -> human review ->
export.**

- The PaymentOps engine performs the deterministic validation and the agent explains the findings.
- The agent proposes a correction only from a supporting-evidence record; the backend checks it.
- Proposed corrections are tested against configured checks on a separate copy, preserving the
  original message for review.
- A person reviews the remaining findings and evidence gaps; nothing is approved automatically.
- Results are exported for the record.

## 4. Product capabilities

- **Synthetic uploads** - an ISO 20022 `pacs.008.001.08` message with an optional, explicitly paired
  supporting-evidence JSON.
- **Deterministic validation** - secure parsing, XSD validation, canonical mapping, versioned rules
  and address-readiness analysis. This is authoritative.
- **Evolus Investigator** - an agent workflow that reads the findings and proposes a correction.
- **AMD Token Factory model connection** - the investigator agent runs on an AMD Token
  Factory-served Gemma-4-31B-IT model.
- **Authenticated validation tool** - the workflow calls back into PaymentOps through a dedicated,
  authenticated tool endpoint.
- **Server-checked proposals** - target, party, value and evidence reference are verified by the
  backend; unsupported or unevidenced changes are rejected.
- **Sandbox repairs** - proposed corrections are tested against configured checks on a separate
  copy, preserving the original message for review.
- **Evidence gaps** - supporting-record gaps, server-derived gaps and agent-reported gaps are shown
  separately from the findings.
- **Dashboard and investigation records** - a tenant-scoped view of runs, findings and corrections.
- **Five-item Batch Exception Desk** - up to five messages per batch, each with its own evidence.
- **Review export** - a tenant-scoped JSON report of findings, proposals and sandbox results.

## 5. Demonstrated outcomes

Verified on the synthetic mixed batch **`bat-479164ac9021`**:

- **Complete evidence:** two warnings -> zero; both towns corrected and the sandbox passed.
- **Incomplete evidence:** the debtor is corrected; the creditor warning remains for review.
- **Clean XML:** no repair needed.
- **Malformed XML:** rejected at upload; the valid items continue.

These are synthetic demonstration results for one batch, not bank-wide accuracy or savings.

## 6. Architecture

- **PaymentOps** - the deterministic engine and the product around it: parsing, XSD validation,
  canonical mapping, rules, address readiness, the authenticated validation tool, server-side
  proposal checks, sandbox re-validation, the operator UI and the batch runner.
- **Evolus** - the agent automation: the investigation workflow, the `PaymentOps Rules` knowledge
  library, and the validation WebAPI the workflow calls back into.
- **AMD Token Factory** - the model inference behind the Evolus investigator agent. PaymentOps does
  not call the model directly; it starts and polls the Evolus workflow.
- **PostgreSQL** - tenant-scoped investigation, repair and batch state (the batch runner is a
  durable task inside the existing API process and persists progress here).

```mermaid
flowchart LR
  U["Operator browser"] --> W["Next.js UI + same-origin proxy"]
  W --> A["FastAPI + PaymentOps engine"]
  A <--> DB[("PostgreSQL")]
  A -->|"start workflow / poll"| E["Evolus workflow"]
  E --> L["PaymentOps Rules library"]
  E -->|"validate-case (tool auth)"| A
  E --> M["AMD Token Factory model (Gemma-4-31B-IT)"]
```

## 7. Deployment pipeline

**GitHub -> GitHub Actions -> GHCR ARM64 -> Flux -> Hetzner K3s.**

- GitHub Actions builds and publishes `linux/arm64` API and web images to GHCR, tagged with the
  commit SHA; the batch of migrate/seed jobs runs against PostgreSQL on rollout.
- Flux reconciles the cluster from the infra repository, pinning immutable image tags (no
  `latest`).
- **Cloudflare Tunnel** terminates public TLS/DNS and forwards to the in-cluster **Envoy Gateway**,
  which routes the hostname to the web service.

## 8. Quick start and configuration

Requirements: Python 3.12+, Node 22+ with pnpm, and Docker for a local PostgreSQL. Run from the
repository root unless noted.

```powershell
# Backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env            # placeholder values only; never commit .env

# PostgreSQL (required)
docker compose up -d postgres

# Schema and seed (run from the API package, where alembic.ini lives)
cd apps\api
alembic upgrade head
python -m scripts.seed_hackathon   # idempotent: demo tenant + operator client + admin user
cd ..\..

# API  (http://localhost:8000)
uvicorn paymentops_api.main:app --host 0.0.0.0 --port 8000

# Web  (http://localhost:3000)
cd apps\web
pnpm install
pnpm dev
```

**Services the current journey requires.** PostgreSQL is required. The AI investigation step also
requires a reachable Evolus workspace and model access; the deterministic validation, proposal
checks and sandbox testing work without it (the investigation step then reports an integration
failure instead of an agent result). Redis and the Celery worker belong to the legacy CSV batch
module and are **not** required for the investigation journey or the Batch Exception Desk.

**Configuration (placeholders only).** The backend reads configuration from the environment, for
example `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`,
and the Evolus settings `EVOLUS_ENABLED`, `EVOLUS_API_KEY`, `EVOLUS_APPLICATION_ID`,
`EVOLUS_WORKFLOW_ID`, `EVOLUS_AGENT_ID`, `EVOLUS_LIBRARY_ID` and `EVOLUS_TOOL_API_KEY`. The web
proxy reads `PAYMENTOPS_INTERNAL_API_URL`, `PAYMENTOPS_CLIENT_ID`, `PAYMENTOPS_CLIENT_SECRET` and
`PAYMENTOPS_OPERATOR_ORG_ID`. The seed step uses `EVOLUS_DEMO_ORG_PUBLIC_ID`,
`PAYMENTOPS_OPERATOR_CLIENT_ID`, `PAYMENTOPS_OPERATOR_CLIENT_SECRET`,
`PAYMENTOPS_BOOTSTRAP_ADMIN_EMAIL` and `PAYMENTOPS_BOOTSTRAP_ADMIN_PASSWORD`. See `.env.example`.
Secrets belong in the local environment or configuration, never in browser code.

## 9. API overview

Operator routes are authenticated by the workspace session through the same-origin `/api/backend`
proxy. The validation tool is authenticated separately with a dedicated tool credential.

| Method and path | Purpose | Auth |
| --- | --- | --- |
| `POST /api/v1/investigations/upload` | Investigate an uploaded synthetic message (+ optional evidence) | Operator |
| `GET /api/v1/investigations` | List the tenant's investigations | Operator |
| `GET /api/v1/investigations/{investigation_id}` | Investigation detail: findings, evidence gaps, proposal | Operator |
| `POST /api/v1/investigations/{investigation_id}/repair/test` | Test the proposed corrections on a sandbox copy | Operator |
| `POST /api/v1/exception-batches` | Submit a batch of up to five paired items | Operator |
| `GET /api/v1/exception-batches` | List the tenant's batches | Operator |
| `GET /api/v1/exception-batches/{batch_id}` | Per-item progress, findings and sandbox state | Operator |
| `POST /api/v1/exception-batches/{batch_id}/items/{item_id}/repair/test` | Sandbox-test one batch item | Operator |
| `GET /api/v1/exception-batches/{batch_id}/export` | Tenant-authorized JSON review report | Operator |
| `POST /api/v1/evolus/tools/validate-case` | Structured validation for the workflow (body `{"case_ref": "<server-issued>"}`) | Tool credential (`X-Tool-Key`) |
| `GET /health`, `GET /ready`, `GET /api/v1/info` | Liveness, readiness and build metadata | Internal / probe |

## 10. Verification

```powershell
# Backend (PostgreSQL required for the integration and security suites)
docker compose up -d postgres
$env:TEST_DATABASE_URL = "postgresql+asyncpg://paymentops:localdev-only@localhost:5432/paymentops"
pytest
ruff check .
ruff format --check .
mypy apps/api/paymentops_api

# Frontend
cd apps\web
pnpm typecheck
pnpm lint
pnpm test
pnpm build
```

## Scope and input limits

Synthetic `pacs.008.001.08` messages, one transaction per XML, with up to five files per batch.
Evidence-linked address corrections checked by the backend.

## Attribution

Third-party components and attached licences are recorded in [`THIRD_PARTY.md`](THIRD_PARTY.md);
those notices and the provenance documentation are preserved unchanged.
