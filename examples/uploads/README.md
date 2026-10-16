# Upload examples (synthetic only)

Downloadable sample bundles for the **Upload synthetic payment** journey on
`/investigations`. All data is **synthetic** — no real payment data.

Each bundle is an ISO 20022 `pacs.008.001.08` XML file plus an optional supporting-evidence
JSON file. The XML is identical in both bundles (debtor and creditor addresses omit `TwnNm`,
producing two `ADR-001` findings); only the evidence differs.

## Bundles

| Bundle | XML | Evidence | Expected outcome |
| --- | --- | --- | --- |
| **complete** (`complete/`) | `pacs008_missing_town.xml` | `evidence.json` (`SR-UP-1`) — debtor `Milano`, creditor `Roma` | Agent proposes both town changes; **Test proposed repair → VALIDATED**; sandbox re-validation clears both `ADR-001`; original unchanged |
| **incomplete** (`incomplete/`) | `pacs008_missing_town.xml` | `evidence.json` (`SR-UP-2`) — debtor `Milano` only | Agent proposes only the debtor change and **must not invent** the creditor town; **Test proposed repair → REVIEW_REQUIRED**; unresolved `ADR-001@Cdtr/PstlAdr` |

## Evidence schema

```json
{
  "record_id": "SR-UP-1",
  "label": "Synthetic account master record (complete)",
  "source": "uploaded synthetic evidence",
  "entries": [
    { "ref": "SR-UP-1:debtor-town", "party": "Dbtr", "field": "TwnNm",
      "value": "Milano", "note": "optional" }
  ],
  "gaps": ["optional free text"],
  "contradictions": ["optional free text"]
}
```

- `entries[].party` ∈ `{Dbtr, Cdtr, DbtrAgt, CdtrAgt}`; `entries[].field` ∈ `{TwnNm, Ctry}`.
- `entries[].ref` must be unique; `value` must be non-empty. Every repair proposal must cite an
  `evidence_ref` whose `party`/`field` **match the target** and whose `value` equals the proposed
  value (values are never invented or derived from a country code).
- Evidence is optional: without it the investigation still runs, but unsupported repairs are
  rejected (human review).

## Limits and safety (enforced server-side)

- XML ≤ 256 KiB; evidence ≤ 64 KiB.
- Safe XML parsing: DTD/entities/network disabled (no XXE); malformed XML rejected.
- Only `pacs.008.001.08` with a **single transaction** is accepted for this journey.
- Uploaded bytes are stored as immutable evidence (base64) under a server-issued reference; the
  filename is never used as a storage path.
- Synthetic data only; credentials remain server-side.

Canonical copies live here; the same files are served for download from
`/examples/uploads/<bundle>/...` (copied into `apps/web/public/examples/uploads/`).
