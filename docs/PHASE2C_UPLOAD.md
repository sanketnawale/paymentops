# Phase 2C — Upload synthetic payment journey

A real upload journey on top of the existing investigation feature. An analyst uploads a
**synthetic** ISO 20022 `pacs.008.001.08` file (plus optional supporting-evidence JSON); the app
stores it as a tenant-scoped case with a server-issued reference and hashes, and the existing
Evolus workflow investigates it (proposal validation → sandbox repair → before/after results).

- **Upload page:** `https://paymentops-hackathon.cloudnova.tech/investigations` (section
  **Upload synthetic payment**). The bundled selection is preserved as **Try a sample**.
- **Sample downloads (public):**
  - Complete: `/examples/uploads/complete/pacs008_missing_town.xml`, `/examples/uploads/complete/evidence.json`
  - Incomplete: `/examples/uploads/incomplete/pacs008_missing_town.xml`, `/examples/uploads/incomplete/evidence.json`
  (canonical copies: `examples/uploads/…`; served from `apps/web/public/examples/uploads/…`.)

## Evidence schema (from the server-side model)

```json
{
  "record_id": "SR-UP-1", "label": "…", "source": "…",
  "entries": [{"ref": "SR-UP-1:debtor-town", "party": "Dbtr", "field": "TwnNm", "value": "Milano", "note": ""}],
  "gaps": [], "contradictions": []
}
```

- `party` ∈ `{Dbtr, Cdtr, DbtrAgt, CdtrAgt}`; `field` ∈ `{TwnNm, Ctry}`; `ref` unique; `value` non-empty.
- Every proposal must cite an `evidence_ref` matching the target party/field and equal to the
  recorded value — values are never invented or derived from a country code.
- Evidence is optional: without it the investigation still runs, but unsupported repairs are
  rejected (human review).

## Behaviour
- `POST /api/v1/investigations/upload` (content-based JSON body `{xml, evidence?, start_workflow}`,
  consistent with the existing `/analyze` pattern). The uploaded bytes are stored base64 as
  immutable evidence under a server-issued `inv-…` reference; **filenames are never storage paths**.
- The validation tool loads the **uploaded** payload (not a demo fixture); `case_origin` is
  `user-uploaded synthetic payload`. Changing the XML changes the validated input hash.
- Limits/safety: XML ≤ 256 KiB; evidence ≤ 64 KiB; safe parsing (DTD/entities/network disabled, no
  XXE); malformed XML rejected; only `pacs.008.001.08`; single transaction (repair limitation).

## Live results (real app → Evolus/AMD → engine)
| Bundle | Investigation | Execution | Outcome |
| --- | --- | --- | --- |
| `complete` | `inv-8d4b7e7c5144` | `ca9d7bce-92c9-f111-bf5b-6045bd9ce552` | Agent proposed `Dbtr/TwnNm=Milano`, `Cdtr/TwnNm=Roma` from `SR-UP-1`; **Test proposed repair → VALIDATED**; sandbox cleared both `ADR-001`; original unchanged |
| `incomplete` | `inv-931821039f8e` | `592b4369-97c9-f111-bf5b-6045bd9ce552` | Agent proposed only `Dbtr/TwnNm=Milano` (`SR-UP-2`) and **did not invent** the creditor town; **Test proposed repair → REVIEW_REQUIRED**; unresolved `ADR-001@Cdtr/PstlAdr` |

Both were driven through the public HTTPS app (`/api/backend` proxy with an authenticated session),
so the frontend→backend path was exercised too.

## Tests
- `tests/unit/test_evidence_schema.py` — evidence schema validation (allowlists, duplicates, round-trip).
- `tests/security/test_upload_journey.py` (DB) — stored payload/tool identity (no demo
  substitution), changing XML changes hash/findings, malformed/unsupported/multi-tx/invalid-
  evidence/oversize rejections, tenant isolation, original immutability.
- Full backend suite: **297 passed**; `ruff` + `mypy` clean; frontend `tsc` + lint clean.

## Deployment
App commits `9c78bbc` (feature) and `dad9eca` (review-status fix) → GHCR (arm64) → Flux
`paymentops-hackathon` (api+web `dad9eca`). Migration `0013_investigation_upload` applied by the
migrate Job. Only the hackathon namespace was touched.

## Notes / limitations
- Removed the `next/font/google` build dependency (`apps/web/app/layout.tsx`) so builds have no
  network dependency on Google Fonts (which intermittently failed CI). Typography now uses the
  system fallback stacks already defined in `globals.css`.
- Uploads are synthetic-only and content-based; only single-transaction `pacs.008.001.08` is
  accepted for this journey. Investigation only — no payment execution or authorization.
