# PaymentOps Rules — knowledge base

> Knowledge-base document for the **PaymentOps Investigator** agent (Evolus).
> Upload this file to the **PaymentOps Rules** library (`language=en`).
> It contains only rules and capabilities verified in the PaymentOps source code. It excludes
> confidential or licensed material.

## 1. What the engine does (and does not do)

- PaymentOps is a **non-transactional** payment-data intelligence platform.
- It runs **deterministic** validation against a canonical payment model.
- Deterministic validation is the **only** authoritative source of truth.
- Generative AI (the investigator) is **advisory only**: it may explain and propose, never
  validate, approve, authorize, or execute.
- Structural/XSD validity is **not** proof of payment safety, settlement, authorization, or
  account ownership.

## 2. Engine and ruleset versions

| Component | Version |
| --- | --- |
| Analysis engine | `0.3.0` |
| Baseline ruleset | `cloudnova-address-v1` |
| Canonical model (payments) | `payment_domain.v2` |
| Canonical model (account reporting) | `payment_domain.v3` |

## 3. Supported ISO 20022 messages (registry)

Dispatch is by exact version resolved from the XML namespace; unsupported versions fail
clearly and are never silently parsed.

| Message | Version |
| --- | --- |
| `pacs.008` | `pacs.008.001.08` |
| `pacs.009` | `pacs.009.001.13` |
| `pacs.002` | `pacs.002.001.16` |
| `pain.001` | `pain.001.001.13` |
| `camt.053` | `camt.053.001.14` |
| `camt.054` | `camt.054.001.14` |

XSD validation is deterministic and runs against the bundled, versioned schema subset.
Schema failures are reported with code `ISO-XSD-001` and a location.

## 4. Baseline rules (deterministic)

Severity levels: `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

### Structural (`ISO-xxx`)

| Rule ID | Name | Severity | Fires when |
| --- | --- | --- | --- |
| `ISO-001` | Instruction ID missing | WARNING | `PmtId/InstrId` absent |
| `ISO-002` | Amount missing | ERROR | `Amt/InstdAmt` absent or non-positive |
| `ISO-003` | End-to-end ID missing | INFO | `PmtId/EndToEndId` absent |

### Semantic consistency (`SEM-xxx`)

| Rule ID | Name | Severity | Fires when |
| --- | --- | --- | --- |
| `SEM-001` | Debtor agent BIC missing | WARNING | `DbtrAgt/FinInstnId/BICFI` absent |
| `SEM-002` | Creditor agent BIC missing | WARNING | `CdtrAgt/FinInstnId/BICFI` absent |
| `SEM-003` | Creditor account missing | WARNING | `CdtrAcct/Id` empty |

### Address readiness (`ADR-xxx`)

| Rule ID | Name | Severity | Fires when |
| --- | --- | --- | --- |
| `ADR-001` | Town name missing | WARNING | `TwnNm` absent when `Ctry` present |
| `ADR-002` | Country missing | ERROR | `Ctry` absent |
| `ADR-003` | Country code invalid | ERROR | `Ctry` is not ISO 3166-1 alpha-2 |
| `ADR-004` | Address is unstructured | WARNING | only `AdrLine` present |
| `ADR-005` | Mixed/hybrid address | INFO | both structured fields and `AdrLine` present |

Field locations are reported as XPath-like targets, e.g. `.../CdtTrfTxInf/Dbtr/PstlAdr`.

## 5. Address readiness outcome values

`READY`, `REPAIRABLE`, `REVIEW_REQUIRED`, `UNRESOLVED`.

The default address provider is deterministic (`CloudNovaAddressProvider`). The development
coverage corpus only covers `IT`, `IN`, `SA`, `GB`, `DE`, `FR`, `ES`, `NL`; other geographies
may return `UNSUPPORTED_GEOGRAPHY` / `UNKNOWN`.

## 6. How to use the validation tool

Call the authenticated PaymentOps tool with a **server-issued** `case_ref`:

```
POST /api/v1/evolus/tools/validate-case
X-Tool-Key: <tool credential>
Content-Type: application/json

{ "case_ref": "<investigation id>" }
```

The response separates:

- `input` — SHA-256 identity and message version (the input is immutable).
- `profile` — ruleset / engine / canonical-model versions.
- `validation` — deterministic status, schema issues, and findings (rule id, severity, target,
  message, evidence, suggested action).
- `interpretation_guidance` — a reminder that deterministic validation is authoritative and
  that it does not establish payment safety or account ownership.

Never pass filesystem paths, URLs, tenant ids, database queries, or credentials in `case_ref`.

## 7. Investigation method (required)

1. Consult this library for the applicable rule identifiers.
2. Call the validation tool with the provided `case_ref`.
3. Report findings that cite the **rule identifiers** and **field locations** returned by the
   tool.
4. State which evidence is **unavailable** and give the **recommended human next step**.
5. Never present structural validity as proof of payment safety or account ownership.

## 8. Escalation conditions (recommend human review)

- Any `ERROR` or `CRITICAL` finding (e.g. `ISO-002`, `ADR-002`, `ADR-003`).
- Schema validation failure (`ISO-XSD-001`).
- An unsupported or unrecognized message version.
- Address readiness of `REVIEW_REQUIRED` or `UNRESOLVED`.
- Missing evidence required to reach a conclusion.

## 9. Out of scope

- No sanctions/AML clearance decisions.
- No payment execution, authorization, release, or settlement.
- No mutation of the original payload (it is immutable evidence).
- No account-ownership or beneficiary-authenticity assertions.
