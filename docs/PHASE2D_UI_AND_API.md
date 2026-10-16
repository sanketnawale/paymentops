# Phase 2D — Hackathon UI, module status, and API access

## 1. UI entry points

| Page | Path | Purpose |
| --- | --- | --- |
| Overview (hackathon) | `/dashboard` | Real investigation counts + prominent **Upload synthetic payment** / **Try a sample** / recent investigations. Existing business-module stats are shown separately and clearly labelled. |
| Investigations | `/investigations` | Upload synthetic payment (XML + optional evidence JSON) and **Try a sample**; sample download links; recent list. |
| Investigation detail | `/investigations/<id>` | Evidence, proposed changes, before/after findings, review status; final report rendered as safe Markdown; raw output/reasoning/XML/hashes collapsed under **Developer diagnostics**. |

Navigation groups investigations first; the copied business modules are grouped under
**Business modules (existing)**.

### Dashboard semantics (no double counting)
- **Completed (workflow)** = the Evolus run finished (`status=COMPLETED`) — *not* a validation result.
- **Sandbox validated** = a proposed repair passed deterministic re-validation on a copy
  (`repair.status=VALIDATED`) — *not* human approval.
- **Review required** = unresolved findings / rejected changes (`repair.status=REVIEW_REQUIRED`).
- Sandbox copies are never counted as executed payments. Business-module counters (analyzed,
  open cases, batches, account reconciliation) are separate and are not populated by investigations.

## 2. Module status in this deployment

Only **Investigations** is integrated with Evolus/AMD. The other modules are the copied PaymentOps
modules and are not wired to the investigator.

| Module | Status in `paymentops-hackathon` | APIs used | Evolus? |
| --- | --- | --- | --- |
| Investigations | Working (Evolus → AMD agent → validation tool → sandbox repair) | `POST /api/v1/investigations`, `/upload`, `GET /api/v1/investigations[/{id}]`, `POST /{id}/repair/test` | **Yes** |
| Analyze (legacy) | Present; **disabled in production** and development/demo only | `POST /api/v1/payments/analyze` | No |
| Cases | Working (real DB, tenant-scoped) | `GET /api/v1/cases[/{id}]`, `POST /api/v1/cases/{id}/actions` | No |
| ISO / lifecycle | Working (real engine + DB) | `POST /api/v1/iso/analyze`, `GET /api/v1/iso/messages`, `/lifecycles` | No |
| Account reporting | Working (real DB) | `GET /api/v1/account-reports`, `/account-entries`, `/account-reconciliations` | No |
| Matching / reconciliation | Working (real engine + DB); needs records to show data | `/api/v1/matching/*`, `/reconciliations` | No |
| Integration profiles / API clients / audit | Working (real DB) | `/api/v1/integration-profiles`, `/clients`, `/audit` | No |
| Batches | **Not functional here**: needs Redis + the Celery worker, which were intentionally not deployed | `POST /api/v1/batches` (enqueues to Redis) | No |

No new batch AI processing was implemented, and none is implied.

## 3. Auth model

- **Operator API** (browser/app): the public route only exposes `/api/v1/evolus/*`. The browser
  reaches operator endpoints via the Next.js proxy `/api/backend/*`, which requires a **session
  cookie** (set at `/api/auth/login`) and a **CSRF token** on mutating calls; the proxy injects the
  server-side operator credential (`X-Client-Id`/`X-Client-Secret`). The backend also accepts
  `X-Client-Id`/`X-Client-Secret` directly for server-to-server use (in-cluster / port-forward).
- **Evolus validation tool** (`/api/v1/evolus/tools/validate-case`) uses a **distinct** credential
  header `X-Tool-Key` (raw `EVOLUS_TOOL_API_KEY`). It is the only endpoint routed publicly.

See the current OpenAPI at `/openapi.json` (development) and `docs/evolus/evolus-workspace-setup.md`.

## 4. Authenticated API examples (credentials via environment variables)

Set privately (never hard-code):

```bash
export PAYMENTOPS_BASE="https://paymentops-hackathon.cloudnova.tech"   # or http://localhost:8000
export PAYMENTOPS_CLIENT_ID="<operator client_id>"
export PAYMENTOPS_CLIENT_SECRET="<operator client_secret>"
export EVOLUS_TOOL_KEY="<EVOLUS_TOOL_API_KEY>"
```

### 4.1 Upload a synthetic payment (operator, direct)
```bash
curl -s -X POST "$PAYMENTOPS_BASE/api/v1/investigations/upload" \
  -H "X-Client-Id: $PAYMENTOPS_CLIENT_ID" -H "X-Client-Secret: $PAYMENTOPS_CLIENT_SECRET" \
  -H "Content-Type: application/json" \
  --data-binary @payload.json
# payload.json: {"xml":"<pacs.008.001.08>...</pacs.008.001.08>","evidence":{...},"start_workflow":true}
```

### 4.2 Investigation status / results (operator)
```bash
curl -s "$PAYMENTOPS_BASE/api/v1/investigations/<investigation_id>" \
  -H "X-Client-Id: $PAYMENTOPS_CLIENT_ID" -H "X-Client-Secret: $PAYMENTOPS_CLIENT_SECRET"
```

### 4.3 Sandbox test of the proposed repair (operator)
```bash
curl -s -X POST "$PAYMENTOPS_BASE/api/v1/investigations/<investigation_id>/repair/test" \
  -H "X-Client-Id: $PAYMENTOPS_CLIENT_ID" -H "X-Client-Secret: $PAYMENTOPS_CLIENT_SECRET" \
  -H "Content-Type: application/json" -d '{}'
```

### 4.4 Validation tool as Evolus calls it (public, tool key)
```bash
curl -s -X POST "$PAYMENTOPS_BASE/api/v1/evolus/tools/validate-case" \
  -H "X-Tool-Key: $EVOLUS_TOOL_KEY" -H "Content-Type: application/json" \
  -d '{"case_ref":"<investigation_id>"}'
```

### 4.5 Through the public web proxy (session + CSRF, what the browser does)
```bash
curl -s -c ck.txt -X POST "$PAYMENTOPS_BASE/api/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"<admin email>","password":"<admin password>"}'
CSRF=$(awk '$6=="paymentops_csrf"{print $7}' ck.txt)
curl -s -b ck.txt -X POST "$PAYMENTOPS_BASE/api/backend/api/v1/investigations/upload" \
  -H "Content-Type: application/json" -H "X-CSRF-Token: $CSRF" --data-binary @payload.json
```

## 5. Verified
- Dashboard counts match the database for the signed-in organization and are tenant-scoped
  (`tests/security/test_dashboard_investigations.py`); JSON `null` sandbox slots are not counted.
- A changed XML `MsgId` yields a different original hash with the same intended findings
  (`tests/security/test_upload_journey.py`).
- Complete/incomplete evidence bundles still produce VALIDATED / REVIEW_REQUIRED (live runs below).
- Backend **298 passed**; `ruff` + `mypy` clean; frontend `tsc` + `next lint` + `next build` pass.

## 6. Live runs (real app → Evolus/AMD → engine)
| Bundle | Investigation | Outcome |
| --- | --- | --- |
| complete | `inv-8d4b7e7c5144` | proposed both towns from `SR-UP-1`; sandbox **VALIDATED** |
| incomplete | `inv-931821039f8e` | proposed debtor town only; **REVIEW_REQUIRED** (no invented creditor town) |

## 7. Limitations
- Batches require Redis + worker (not deployed). Analyze is development/demo-only.
- Only Investigations integrates with Evolus/AMD. Uploads are synthetic-only, content-based,
  `pacs.008.001.08`, single-transaction.
- A sandbox passing the selected deterministic checks is **not proof of full address correctness**
  or payment safety.
