# Evolus workspace setup (Phase 1)

Manual configuration for the **PaymentOps Investigator** in your Evolus workspace. The
backend integration is already implemented; these steps configure the two Evolus building
blocks (a **knowledge library** and a **workflow**) plus the agent's **validation WebAPI tool**.

All credentials stay server-side (`.env`, never committed). The browser never receives keys.

## Verified contract (from https://evolus.ai/developers)

| Concern | Value |
| --- | --- |
| REST base URL | `https://api.evolus.ai/api/v1` |
| REST auth headers | `X-ApiKey: <application API key>`, `X-Application-Id: <space id>` |
| Start workflow | `POST /workflows/{workflowId}/execute` (multipart: `input`, optional `parameters`) |
| Start response | `202` + `{jobId, executionId, enqueuedAt, traceId}` and `X-Workflow-Execution-Id` |
| Read run | `GET /workflows/{workflowId}/executions/{executionId}` (`status`: Pending/Running/Completed/Failed) |
| Libraries | `POST /memories/{libraryId}/documents?language=en` (multipart `file`) |
| Rate limit | 60 requests/min per workspace; honour `429` + `Retry-After` |

> **Not fully public:** the exact JSON body of a *completed* execution. The backend parses it
> defensively (it looks for `output`/`result`/`data`/`answer`/`content`/`text`/`message`) and
> preserves the raw body. Confirm the actual shape in your workspace's interactive API
> reference and, if needed, adjust `EvolusClient._extract_output`.

## 1. API key and space id

1. In the workspace, open **API keys**.
2. Create an application API key. Copy the key and the **space id** shown on the same page.
3. Set them in `.env` (server-side only):

```
EVOLUS_ENABLED=true
EVOLUS_API_KEY=<application API key>
EVOLUS_APPLICATION_ID=<space id>
```

## 2. Model (AMD Token Factory)

The agent runs on your team's model. The connection already exists:

- Provider base URL: `https://developer.amd.com.cn/radeon/api/v1`
- Model: `Gemma-4-31B-IT`

Confirm the model connection under **Your models** and select it in the agent. The model API
key is configured in Evolus (not in PaymentOps); do not copy it into this repository.

## 3. Knowledge library: "PaymentOps Rules"

1. Create a library named **PaymentOps Rules**.
2. Upload `docs/evolus/paymentops-rules-knowledge-base.md` as a document with `language=en`
   (either through the workspace UI, or via the REST API):

```
curl -X POST "https://api.evolus.ai/api/v1/memories/$LIBRARY_ID/documents?language=en" \
  -H "X-ApiKey: $EVOLUS_API_KEY" \
  -H "X-Application-Id: $EVOLUS_APPLICATION_ID" \
  -F "file=@docs/evolus/paymentops-rules-knowledge-base.md"
```

3. Wait until the document reports **indexed**, then note the library id:

```
EVOLUS_LIBRARY_ID=<library id>
```

## 4. Agent: "PaymentOps Investigator"

The agent already exists. Verify/attach:

1. Attach the **PaymentOps Rules** library.
2. Attach the **PaymentOps Validate Case** tool (section 5).
3. Instruct the agent to: consult the library, call the validation tool with the run's
   `case_ref`, cite rule identifiers and field locations, list missing evidence, and give a
   recommended human next step; never present structural validity as proof of payment safety.

Note the agent id:

```
EVOLUS_AGENT_ID=<agent id>
```

## 5. Validation WebAPI tool: "PaymentOps Validate Case"

Expected tool configuration (HTTP/WebAPI tool):

- Method: `POST`
- URL: `<PaymentOps base URL>/api/v1/evolus/tools/validate-case`
- Header: `X-Tool-Key: <EVOLUS_TOOL_API_KEY>`
- Body (JSON): `{ "case_ref": "<the investigation id provided in the run input>" }`

Set the shared credential in `.env` on the PaymentOps side:

```
EVOLUS_TOOL_API_KEY=<a long random secret you generate>
```

> **Reachability requirement.** Evolus is a cloud service, so it can only call a publicly
> reachable PaymentOps URL. Locally this is not reachable; use an HTTPS tunnel for a local
> demo, or deploy in Phase 2. Until then the workflow can still run (the agent will report the
> tool as unavailable), and the deterministic findings are already shown in the PaymentOps UI.
>
> The exact field names in the tool configuration screen are **not documented publicly**;
> configure them to produce the HTTP request above. If your workspace's tool editor differs,
> report the difference and we will adjust.

## 6. Workflow: "PaymentOps Investigation"

Create a workflow with:

1. A **manual/API trigger** (so it can be started by `POST .../execute`). Its input is the text
   built by the backend (it contains `case_ref` and `message_version`; no secrets, no payload).
2. An **agent step** using **PaymentOps Investigator** (library + tool attached). Ask it to
   return JSON:

```json
{
  "explanation": "…",
  "cited_rules": ["ADR-001"],
  "missing_evidence": ["…"],
  "recommended_next_step": "…"
}
```

   If the agent returns plain text instead, PaymentOps still extracts rule identifiers
   (`ISO-###`, `SEM-###`, `ADR-###`) from the text as a fallback.

3. Enable the workflow (**a disabled workflow returns `409 Conflict`**).
4. Note the workflow id:

```
EVOLUS_WORKFLOW_ID=<workflow id>
```

## 7. Run it

1. Start PaymentOps and the web app (see `docs/PHASE1.md`).
2. In the app, open **Investigations**, choose a synthetic demo case, and click **Investigate**.
3. The backend runs the deterministic engine, starts the workflow once, and polls the run.
4. The UI shows deterministic findings, progress, the agent's explanation and cited rules,
   missing evidence, and the recommended next step.

## Missing information to confirm with the workspace owner

- `EVOLUS_APPLICATION_ID`, `EVOLUS_API_KEY` (secret — enter locally).
- `EVOLUS_WORKFLOW_ID`, `EVOLUS_AGENT_ID`, `EVOLUS_LIBRARY_ID`.
- The exact **completed-execution response schema** (from the in-workspace API reference).
- The exact **WebAPI tool configuration** fields.
