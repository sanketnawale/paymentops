# Demo Runbook - PaymentOps hackathon build

Audience: demo presenters and judges. No credentials or secrets are stored in this file; operator
credentials are injected at runtime from the cluster secret (see "Access" below).

> Synthetic data only. PaymentOps never executes, authorizes or settles payments; repairs are
> tested on sandbox copies and the original payload is never modified.

## 1. URLs

| Purpose | URL |
| --- | --- |
| App (same-origin UI + authenticated API proxy) | `https://paymentops-hackathon.cloudnova.tech` |
| Sign in | `https://paymentops-hackathon.cloudnova.tech/login` |
| Single-file investigations | `https://paymentops-hackathon.cloudnova.tech/investigations` |
| Batch Exception Desk | `https://paymentops-hackathon.cloudnova.tech/batches/exceptions` |
| A specific investigation | `/investigations/<investigation_id>` (e.g. `/investigations/inv-a0d10c02d6e6`) |
| Deep link to a batch | `/batches/exceptions` then select the batch in **Recent batches** |

Health/info are behind the session proxy: `/api/backend/health`, `/api/backend/ready`,
`/api/backend/api/v1/info`.

## 2. Access

- Sign in with the workspace operator account (email + password). Both are read from the
  Kubernetes secret `paymentops-hackathon-bootstrap` in namespace `paymentops-hackathon`; do not
  copy them into this file or into any recording.
- The browser only ever talks to the same-origin proxy; the internal API URL, operator credential
  and Evolus/AMD keys never reach the browser.

## 3. Known verified case IDs and expected outcomes

These were produced by live Evolus/AMD runs and are safe to reuse as read-only references.

### Batch `bat-479164ac9021` - four-outcome mixed batch

Rejected-item UI and the export both match these recorded results:

| Item | File | Investigation | Expected outcome |
| --- | --- | --- | --- |
| 1 | `complete.xml` (complete evidence) | `inv-a0d10c02d6e6` | 2 findings; proposed `Dbtr/PstlAdr/TwnNm=Milano`, `Cdtr/PstlAdr/TwnNm=Roma`; sandbox **VALIDATED** (2 findings -> 0) |
| 2 | `incomplete.xml` (debtor-only evidence) | `inv-4175f9227cbc` | 2 findings; proposed `Dbtr/PstlAdr/TwnNm=Milano` only; sandbox **REVIEW_REQUIRED** (creditor `ADR-001@Cdtr/PstlAdr` remains unresolved) |
| 3 | `clean.xml` | `inv-ace6516d4b54` | no findings -> **No repair needed** |
| 4 | `bad.xml` (malformed) | none | **Rejected at upload** - `rejected (MalformedXmlError): XML could not be parsed`; other items continue |

Batch status: **PARTIAL** (3 completed, 1 rejected). The review export label is
`paymentops.batch_exception_review` with `synthetic: true`.

### Single-file journeys

| Investigation | Case | Expected outcome |
| --- | --- | --- |
| `inv-15e8c3d13f91` | incomplete evidence | debtor-only repair proposed; sandbox **REVIEW_REQUIRED**; creditor `ADR-001` remains |
| `inv-73f627159450` | complete evidence | both towns proposed; sandbox **VALIDATED** (0 findings after) |
| `inv-f767750288ed` | incomplete evidence (fresh) | one creditor gap surfaced; one `ADR-001@Cdtr/PstlAdr` remains |
| `inv-36d4e1d8b847` | diagnostic | agent-reported gaps captured; a server-derived creditor gap is shown alongside the supporting-record gaps |

Sample bundles are downloadable from the `/investigations` page:
`/examples/uploads/complete/{pacs008_missing_town.xml,evidence.json}` and
`/examples/uploads/incomplete/{pacs008_missing_town.xml,evidence.json}`.

## 4. Recording steps

1. **Intro (30s)** - state the problem (manual exception triage) and the loop: deterministic
   engine -> Evolus/AMD investigator -> evidence-backed proposal -> sandbox re-validation.
2. **Single-file (3-4 min)** - open `/investigations`, start the **incomplete** sample (upload the
   XML + evidence), and show:
   - deterministic findings and address readiness (authoritative engine output);
   - the investigator report (agent interpretation) and its evidence gaps;
   - **Test proposed repair** -> review status **REVIEW_REQUIRED** and the remaining
     `ADR-001@Cdtr/PstlAdr` finding, with the note that the original hash is unchanged.
3. **Single-file clean case (1 min)** - upload the **complete** sample and show **VALIDATED**
   (2 findings -> 0).
4. **Batch Exception Desk (3-4 min)** - open `/batches/exceptions`, submit four rows
   (complete, incomplete, a clean XML, and one malformed XML), then show:
   - sequential per-item progress (one model run at a time);
   - item 4 flagged **Rejected at upload** with its reason while the others continue;
   - **Test supported repairs** on items 1 and 2 (VALIDATED vs REVIEW_REQUIRED);
   - **Review export** downloads the JSON report (statuses, hashes, proposed vs tested changes).
5. **Close** - reiterate: synthetic data only, no payment is executed, and the agent is
   non-authoritative.

Keep runs short: model latency varies. Prefer reusing the verified IDs above for anything you do
not need to run live.

## 5. Backup results (if live runs are slow or rate-limited)

If a live model run is unavailable during recording (rate limit, workspace hiccup, slow latency),
open the **verified case IDs from section 3** instead and say clearly:

> "This is a pre-recorded result from the same build; I am showing it as a backup because the
> shared model is rate-limited right now."

Label every fallback explicitly as **pre-recorded backup**. Do not present a recorded result as a
fresh live run, and do not manufacture latency, savings or success rates.

## 6. Troubleshooting

- **Rate limit (HTTP 429 / "Retry after Ns").** The backend respects `Retry-After` and poll
  backoff. Batch items and investigations stay `RUNNING` and are re-polled automatically; the page
  refreshes itself. Wait for the indicated time and refresh. Do not resubmit - the batch
  `idempotency_key` returns the existing batch instead of starting new runs.
- **Evolus workflow unavailable or not configured.** An investigation shows `FAILED` with
  "Evolus integration is not configured ..." or a workflow error. The deterministic engine,
  proposals and sandbox testing still work. To demo the agent step, confirm the workspace is
  enabled and the `EVOLUS_*` values (API key, application id, workflow id, tool key) are present
  in the cluster secret `paymentops-hackathon-secrets`; a workspace/agent change is applied in the
  Evolus UI (editing a local document does not update the workspace).
- **Batch item stuck, or failed as "ambiguous".** The durable runner advances work server-side;
  a refresh does not change progress. If the API pod restarts while starting a workflow, the item
  is deliberately marked **failed (ambiguous)** rather than starting a duplicate external run -
  resubmit it as a new item.
- **"Test supported repairs" is disabled.** The item is not yet `COMPLETED`, has no
  server-validated proposal, or was already sandbox-tested. A clean item shows
  **No repair needed** and has nothing to test.
- **Sign-in loop / 401.** The session expired; sign in again. All API calls must go through the
  same-origin proxy (`/api/backend/...`); direct backend URLs are not exposed.

## 7. Rollback (GitOps)

The deployed build is pinned by immutable image tags; roll back by re-pinning to the recorded
versions - never by deleting data.

- **Recorded good versions** (tested application commit `2136588`):
  - `ghcr.io/sanketnawale/paymentops-hackathon-api:21365882494475303e85fc161e3589c8b80ff864`
  - `ghcr.io/sanketnawale/paymentops-hackathon-web:21365882494475303e85fc161e3589c8b80ff864`
- **Rollback steps** (infra repo `loudnova-infra`, cluster `hetzner-dr` only):
  1. In `clusters/hetzner-dr/apps/paymentops-hackathon/overlays/dr/kustomization.yaml`, set both
     `newTag` values to the recorded tag above.
  2. Commit and push to the infra repo `main`.
  3. Force a reconcile:
     `kubectl --kubeconfig "$HOME\.kube\hetzner-dr.yaml" -n flux-system annotate kustomization/paymentops-hackathon reconcile.fluxcd.io/requestedAt="$(date -u +%Y-%m-%dT%H:%M:%SZ)" --overwrite`
  4. Confirm the API and web Deployments reach `1/1` and `/api/backend/ready` returns ready.

Rolling back the image does not revert the database schema. Migrations are additive; the recorded
version runs against a schema that is at least its own Alembic head. Do not drop tables or delete
records as part of a rollback.

## 8. Deployment reference

- App commit tested and deployed: `2136588` (images `21365882494475303e85fc161e3589c8b80ff864`).
- Flux Kustomization `paymentops-hackathon` in namespace `flux-system`; cluster `hetzner-dr`.
- Migration head: `0014_batch_exception_desk` (additive).
- Scope: namespace `paymentops-hackathon` only. The marketing site `paymentops-site` and all other
  workloads are untouched.
