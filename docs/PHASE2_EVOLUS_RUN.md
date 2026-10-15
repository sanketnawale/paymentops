# Phase 2B — Live Evolus/AMD investigation run

Record of the first **app-driven** real investigation through Evolus (AMD Token Factory,
`Gemma-4-31B-IT`) after the hackathon deployment. No secrets are included.

## Deployment context
- App: `https://paymentops-hackathon.cloudnova.tech` (namespace `paymentops-hackathon`)
- Workflow: `af52e17d-4f3c-4c57-817c-fe50c624ccb7` ("PaymentOps Investigation"), `isActive=true`
- Agent: PaymentOps Investigator; knowledge library "PaymentOps Rules"; Validation WebAPI attached

## Real run
| Item | Value |
| --- | --- |
| Investigation | `inv-6778d87ef05a` |
| Evolus execution | `ac6ad082-c3c8-f111-bf5b-000d3aae6dc8` |
| Status | `COMPLETED` (Evolus `status=Completed`, `error=[]`, `totalStepsExecuted=2`) |
| Trigger | App `POST /api/v1/investigations {"demo_case_key":"pacs008-missing-town","start_workflow":true}` |

### Observed Evolus response shape (used to fix the client, not assumed)
- `POST /workflows/{id}/execute` → `202` with `{jobId, executionId, enqueuedAt, traceId}`.
- `GET /workflows/{id}/executions/{executionId}` → top-level keys include
  `id, workflowId, input, output, stepOutputs, status, error, totalStepsExecuted,
  requestedAt, completedAt, traceId, stepStates, consumption`.
  - `output`: **string** — the agent text, which contains its **reasoning narration inline**
    followed by the report. There is **no separate reasoning field** (`stepOutputs["1"]` and
    `stepOutputs["2"]` are identical to `output`). We therefore **preserve** the full text and
    do **not** apply a broad text filter (which could delete legitimate report content).
  - `error`: a **list** (`[]` on success) — now surfaced for failures.
  - `status`: `Completed` / `Failed` / etc.

### Tool-call evidence (genuine)
- API log: `10.42.0.12 (Envoy data-plane) - "POST /api/v1/evolus/tools/validate-case" 200 OK`
- Audit event: `investigation.validation_tool` for `inv-6778d87ef05a`, `result=valid`
  (via `GET /api/v1/audit`).
- Findings **agree with the engine**: two `ADR-001` warnings (`Dbtr/PstlAdr`, `Cdtr/PstlAdr`),
  `identity_sha256 a78e9098…` matching the stored input hash, `address_readiness=REVIEW_REQUIRED`,
  schema valid (`pacs.008.001.08`). The agent's report recommends opening a human-review case
  and explicitly avoids payment-safety/account-ownership claims.

## Parser/polling fixes (from observed responses)
- `WorkflowExecution` now carries `error_text` and `trace_id`; failure messages come from the
  real `error` list (previously a generic message).
- `_extract_output` falls back to `stepOutputs` when `output` is absent.
- `traceId` is captured from the execution body into the investigation.
- "Cited rules" extraction ignores **markdown table rows**, so echoing the rules catalogue
  (`| \`ADR-002\` | … |`) no longer produces bogus citations; real findings (`ADR-001`) are kept.
  The report text itself is never filtered.
- Regression tests: `tests/unit/test_evolus_client.py` (real completed/failed/step-fallback
  shapes) and `tests/unit/test_investigation_validation.py` (rule-catalogue table ignored,
  reasoning preserved).

## Limitations
- The agent emits reasoning inline in `output`; we preserve it rather than risk dropping content.
- Address coverage remains the dev corpus (IT/IN/SA/GB/DE/FR/ES/NL); `REVIEW_REQUIRED` is expected.
- Investigation only — no sandbox repair/revalidation, no payment execution.
- Live model output can vary between runs; deterministic engine findings remain authoritative.
- Earlier failed investigations (`inv-04ccde39fa6e` = invalid key; `inv-f7cc01052234` = workflow
  off) were deliberately left as visible failures.
