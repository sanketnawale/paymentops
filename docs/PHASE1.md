# Phase 1 — Evolus integration & AMD-powered investigator

Phase 1 adds an **investigation-only** capability to PaymentOps. An analyst loads a synthetic
ISO 20022 case and clicks **Investigate**; the backend runs the deterministic engine, starts an
Evolus workflow whose **PaymentOps Investigator** agent consults a knowledge library and calls
an authenticated PaymentOps validation tool, and the UI shows evidence-backed findings.

Phase 1 does **not** apply repairs, does **not** execute or authorize payments, and does **not**
deploy anything. Repair/sandbox revalidation and cluster deployment are Phase 2.

## 1. Reused PaymentOps foundation

This work reuses the copied PaymentOps application without forking architecture:

- **FastAPI API** (`apps/api`): routers, tenant-scoped auth (`X-Client-Id`/`X-Client-Secret`),
  structured settings/logging, Prometheus metrics, Alembic migrations.
- **Deterministic engine**: `analysis.AnalysisPipeline` + `iso_engine` registry (secure parse →
  identify → XSD validate → canonical map → `rules_engine` → address readiness). Engine `0.3.0`,
  baseline ruleset `cloudnova-address-v1`.
- **Next.js frontend** (`apps/web`): server-side auth proxy (`/api/backend/*`), RBAC, shared UI
  components, status/badge system.
- **Persistence patterns**: org-scoped tables, JSONB metadata, append-only audit events.

New AI logic is deliberately thin: a REST client + a workflow orchestration service. No MCP
server, sub-agents, or new infrastructure services were introduced.

## 2. What was added

### Backend

| Area | Files |
| --- | --- |
| Evolus REST client | `apps/api/paymentops_api/evolus/client.py` |
| Demo-case registry | `apps/api/paymentops_api/evolus/demo_cases.py` |
| Synthetic demo payloads | `apps/api/paymentops_api/demo_data/*.xml` (+ `README.md`) |
| Investigation model | `apps/api/paymentops_api/db/models/investigation.py` |
| Migration | `apps/api/alembic/versions/0011_investigations.py` |
| Orchestration service | `apps/api/paymentops_api/services/investigation_service.py` |
| API + tool router | `apps/api/paymentops_api/routers/investigations.py` |
| Config / logging / metrics | `settings.py`, `logging.py`, `observability.py`, `app/factory.py` |

### Frontend

- `apps/web/app/investigations/page.tsx` — choose a synthetic case and start an investigation.
- `apps/web/app/investigations/[id]/page.tsx` — progress, deterministic findings, agent output.
- `apps/web/lib/api.ts` — investigation API client.
- `apps/web/components/AppShell.tsx`, `middleware.ts` — nav + route protection.
- `apps/web/lib/investigations.test.ts` — API client tests.

### Docs

- `docs/evolus/paymentops-rules-knowledge-base.md` — the knowledge-library document.
- `docs/evolus/evolus-workspace-setup.md` — manual Evolus configuration.
- This file.

## 3. API contracts

### Verified (public Evolus documentation)

- Base URL `https://api.evolus.ai/api/v1`; auth `X-ApiKey` + `X-Application-Id`.
- `POST /workflows/{workflowId}/execute` (multipart `input`) → `202` +
  `{jobId, executionId, enqueuedAt, traceId}` and `X-Workflow-Execution-Id`.
- `GET /workflows/{workflowId}/executions/{executionId}` → `status` ∈
  `Pending | Running | Completed | Failed`.
- Library upload `POST /memories/{libraryId}/documents?language=en`.
- Workspace limit 60 requests/min; `429` carries `Retry-After`.

### PaymentOps endpoints (this repo)

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/v1/investigations/demo-cases` | operator | List synthetic demo cases |
| POST | `/api/v1/investigations` | operator | Start an investigation |
| GET | `/api/v1/investigations` | operator | List investigations (tenant-scoped) |
| GET | `/api/v1/investigations/{id}` | operator | Detail (polls Evolus while running) |
| POST | `/api/v1/evolus/tools/validate-case` | tool credential (`X-Tool-Key`) | Deterministic validation |

The tool request body is `{ "case_ref": "<server-issued id>" }`; the caller cannot supply
filesystem paths, URLs, tenant ids, queries, or credentials.

## 4. Environment variables

See `.env.example` (Evolus section). Key variables:

| Variable | Meaning |
| --- | --- |
| `EVOLUS_ENABLED` | Master switch (default `false`; core product works without AI) |
| `EVOLUS_API_BASE_URL` | REST base URL (default `https://api.evolus.ai/api/v1`) |
| `EVOLUS_API_KEY` | Application API key (secret, server-side) |
| `EVOLUS_APPLICATION_ID` | Workspace/space id (`X-Application-Id`) |
| `EVOLUS_WORKFLOW_ID` | Investigation workflow id |
| `EVOLUS_AGENT_ID` / `EVOLUS_LIBRARY_ID` | Inventory (recorded for audit) |
| `EVOLUS_TOOL_API_KEY` | Inbound validation-tool credential (secret, server-side) |
| `EVOLUS_REQUEST_TIMEOUT_SECONDS` / `EVOLUS_POLL_TIMEOUT_SECONDS` | Bounded timeouts |
| `EVOLUS_POLL_INTERVAL_SECONDS` / `EVOLUS_MAX_RETRIES` | Polling cadence and retries |
| `EVOLUS_DEMO_ORG_PUBLIC_ID` | Optional tool tenant guard |

## 5. Safety and security decisions

- **Engine authoritative**: deterministic validation is the source of truth; the agent only
  interprets.
- **No raw payload persisted** for real data; investigations store a bundled synthetic
  demo-case key + SHA-256 identity, and structured findings/results.
- **Immutable input**: the tool never mutates the payload; it returns the SHA-256 identity and
  an `input_unchanged` flag.
- **Narrow tool scope**: only server-issued `case_ref` values referencing bundled synthetic
  cases; optional demo-org tenant guard.
- **Dedicated tool credential** compared with `hmac.compare_digest`; a distinct secret from the
  operator client. Unconfigured tool returns `503`; bad/missing key returns `401`.
- **No duplicate runs**: workflow-start requests are never retried; only status polling
  retries, honouring `Retry-After` with bounded backoff.
- **Failures are visible**: integration failures surface as explicit `FAILED` state + message;
  nothing is silently substituted with a local model or a stub labelled as live.
- **Secrets never leave the server**: settings expose only booleans; the logging redactor masks
  `api_key`/`apikey`/`X-ApiKey`/`authorization`/`evolus_*` fields.
- **No execution surface**: no payment execution, mutation, shell, or DB-admin endpoints.

## 6. Run locally

Backend (Python 3.12+):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
copy .env.example .env
# run migrations against your local Postgres, then:
.\.venv\Scripts\python.exe -m uvicorn paymentops_api.main:app --port 8000
```

Frontend (Node 22+ / pnpm):

```powershell
cd apps/web
pnpm install --frozen-lockfile
pnpm dev    # http://localhost:3000
```

With `EVOLUS_ENABLED=false`, investigations still run the deterministic engine and record a
visible integration failure for the agent step.

## 7. Blockers / missing configuration

The independent local implementation is complete. The **live** Evolus/AMD path needs the
workspace owner to supply non-secret identifiers and enter secrets locally:

1. `EVOLUS_APPLICATION_ID` (space id) and `EVOLUS_API_KEY` (secret).
2. `EVOLUS_WORKFLOW_ID` (and `EVOLUS_AGENT_ID`, `EVOLUS_LIBRARY_ID`).
3. The exact **completed-execution response schema** from the in-workspace API reference.
4. The exact **WebAPI tool configuration** fields.
5. A publicly reachable PaymentOps URL for the tool (Phase 2 deploy, or an HTTPS tunnel).

Until (1)–(5) are provided, the AMD model is **not** invoked by this repository, and no result
is labelled as live.

## 8. Third-party / licence note

This phase adds no third-party code or datasets. The vendored Swift component under
`third_party/` is unchanged; its redistribution/licence status is inherited from
`THIRD_PARTY.md` and must be reviewed before any public publication. No licence is claimed as
cleared here.
