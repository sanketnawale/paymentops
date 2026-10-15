# Phase 2B — Evidence-supported sandbox repairs

One complete scenario (repairable) plus a second (incomplete evidence) run **live** through the
app → Evolus workflow → AMD `Gemma-4-31B-IT` → PaymentOps validation tool → sandbox repair.
No secrets are included. Investigation only: no payment execution, no authorization.

## Safety model
- The agent may only **propose** changes: `{target, value, evidence_ref}` where `target` is a
  party-scoped field (`Dbtr/PstlAdr/TwnNm`). The **server resolves the real XML path** itself.
- Targets are allowlisted (`Dbtr|Cdtr|DbtrAgt|CdtrAgt` × `PstlAdr` × `TwnNm|Ctry`). Values must
  **equal the recorded evidence value**; the `evidence_ref` must exist and match the target's
  party/field. Unsupported/conflicting/cross-party changes are rejected.
- The sandbox is produced by the existing `repair_engine` (deep copy; only allowlisted
  `PostalAddress24` leaves are created). The **original payload is never mutated**.
- The sandbox is re-validated by the **real deterministic engine** (XSD + rules + address).
  Passing validation is **not** payment authorization, settlement readiness, or proof of safety.

## Evidence
Synthetic supporting records (clearly labelled, never real data), explicitly linked to a party:
- `pacs008-missing-town` → `SR-1` with `SR-1:debtor-town` (Dbtr/TwnNm=Milano) and
  `SR-1:creditor-town` (Cdtr/TwnNm=Roma).
- `pacs008-missing-town-incomplete` → `SR-2` with only `SR-2:debtor-town` (Dbtr/TwnNm=Milano),
  plus `gaps` and `contradictions` notes (no creditor town, contradictory note).

## Scenario 1 — repairable (live, VALIDATED)
| Item | Value |
| --- | --- |
| Investigation | `inv-aa53dd62ac76` |
| Evolus execution | `202be765-d2c8-f111-bf5b-000d3aae6dc8` |
| Agent proposal | `Dbtr/PstlAdr/TwnNm=Milano` (`SR-1:debtor-town`), `Cdtr/PstlAdr/TwnNm=Roma` (`SR-1:creditor-town`) |
| Repair status | `VALIDATED`; `review_status=VALIDATED`; `xsd_valid=true` |
| Applied (sandbox) | both town names |
| Findings | original `ADR-001 ×2` → sandbox **none** |
| Hashes | original `a78e9098…` (unchanged); sandbox `8190e558…` |
| Re-validated by | `paymentops-engine 0.3.0` |

## Scenario 2 — incomplete/contradictory evidence (live, REVIEW_REQUIRED)
| Item | Value |
| --- | --- |
| Investigation | `inv-e4aaf3e14960` |
| Evolus execution | `1ab2fffc-d4c8-f111-bf5b-000d3aae6dc8` |
| Agent proposal | only `Dbtr/PstlAdr/TwnNm=Milano` (`SR-2:debtor-town`) — **no creditor town invented** |
| Repair status | `REVIEW_REQUIRED`; unresolved `ADR-001@Cdtr/PstlAdr` surfaced |
| Hashes | original `a78e9098…`; sandbox `971f2dfe…` |

The engine requires review whenever **any original finding remains** after the sandbox apply
(fixed after an initial miss where only targeted fields were checked). The creditor town has no
evidence and is never invented.

## Tool-call evidence (genuine)
API logs show `POST /api/v1/evolus/tools/validate-case` → `200 OK` from the Envoy data plane for
each run; audit records `investigation.validation_tool` (`result=valid`) per investigation.

## Output cleanup
- The agent's reasoning arrives **inline in `output`** (no separate field). We preserve the raw
  output server-side and expose a **final answer** (`answer_text`) split at the first markdown
  heading via a narrow parser. When no reliable boundary exists, `answer_separation_reliable=false`
  is set and the UI **flags** it — nothing is silently deleted.
- Agent-mentioned rule ids (`agent_rule_mentions`) are kept **separate** from engine-reported ids
  (`engine_rule_ids`). `agreement_rules` is their intersection. A matching rule id is agreement,
  not proof the explanation is correct.

## Evolus configuration
No Evolus UI change was required: the proposal JSON contract is included in the workflow **input**
built by the app (the public docs expose no workflow structured-output parameter; the step's
`outputStructureId` is workspace-side). If a future workspace wants native structured output, set
the agent step's response format to the schema in `repair_service.build_proposal_contract()` — this
is optional; the app parses the fenced JSON block regardless.

## Deployment
- App commits: `cff57ce` (feature), `a49dcc5` (review fix). Images published to GHCR; deployed via
  Flux to `paymentops-hackathon` (api `a49dcc5`, web `cff57ce`). Migration `0012_investigation_repair`
  applied by the migrate Job (adds `supporting_record`, `repair`, `answer_text`).
- The arm64 **web** image for `a49dcc5` failed on a flaky `next/font` Google-Fonts fetch at build
  time (external); the API fix deployed against the previous, equivalent web image. The only web
  delta is a cosmetic "Unresolved" line.

## Limitations
- Investigation/repair-candidate only; no payment execution or authorization.
- Repair supports single-transaction messages; only address leaves `TwnNm`/`Ctry` are proposeable.
- Agent output quality varies (sometimes Italian; reasoning inline); engine findings are authoritative.
- `additionalProperties`/schema of the model proposal is enforced by our parser, not by Evolus.
