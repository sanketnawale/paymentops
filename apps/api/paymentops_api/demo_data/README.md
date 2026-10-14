# PaymentOps demo data (synthetic)

Bundled synthetic ISO 20022 payloads used by the Phase 1 investigation demo. They are
**not** real payment data and contain only well-known public test identifiers
(e.g. the ISO 13616 example IBANs).

## Origin

These files are copies of existing PaymentOps synthetic test fixtures, reused so the demo
does not introduce new data:

| Demo file | Origin | Notes |
| --- | --- | --- |
| `pacs008_valid.xml` | `tests/fixtures/pacs008/valid_structured.xml` | Structured address, no expected rule findings. |
| `pacs008_missing_town.xml` | `tests/fixtures/pacs008/missing_town.xml` | Triggers the deterministic `ADR-001` (town name missing) finding. |
| `pacs008_hybrid_address.xml` | `tests/fixtures/pacs008/hybrid_address.xml` | Triggers the deterministic `ADR-005` (hybrid address) finding. |

## Handling rules

- Treated as **untrusted input** (AGENTS.md rule 3) and passed through the same secure
  parse / XSD validation as any other payload.
- **Immutable evidence** (AGENTS.md rule 4 / ADR-006): never mutated at runtime.
- Only these server-side, registry-referenced files may be validated by the Evolus tool;
  callers cannot supply filesystem paths or URLs.
