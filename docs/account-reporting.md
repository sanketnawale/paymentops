# Account Reporting (camt.053 / camt.054)

PaymentOps analyzes bank account reporting as **evidence only**. It never debits, credits,
settles, or modifies a bank ledger. camt.053 and camt.054 are parsed deterministically; no LLM
is used for parsing, correlation, or reconciliation.

## Purpose

- **camt.054** (`BankToCustomerDebitCreditNotificationV14`) — a debit/credit notification:
  individual account movements reported by the account servicer.
- **camt.053** (`BankToCustomerStatementV14`) — an account statement: opening/closing balances
  plus booked entries for a period.

Both normalize their `Ntry` records into the same canonical **`AccountEntry`**, so the same
reconciliation logic works for both. A single camt message may contain multiple
statements/notifications and multiple entries; none of them is assumed to be one event.

## Account-entry identity

Deterministic identity uses the strongest available identifiers, in order: account servicer
reference, transaction ID, end-to-end ID, UETR, instruction ID, entry reference, then
amount/currency/credit-debit context. Fuzzy party names are never used to establish identity.

## Correlation to payment lifecycles

Account entries are correlated to existing `PaymentLifecycle` records using a strict identifier
hierarchy:

1. UETR exact
2. transaction ID exact
3. end-to-end ID exact
4. instruction ID exact
5. account servicer reference (where appropriate)
6. normalized external/remittance reference
7. amount + currency + account context
8. Week 4 matching primitives as a controlled fallback

Fuzzy party-name similarity alone never establishes a final correlation.

## Reconciliation classifications

| Classification | Meaning |
|----------------|---------|
| `RECONCILED` | Strong identifiers + amount + currency agree; no critical conflict |
| `POSSIBLE_RECONCILIATION` | Partial evidence (e.g. amount+currency or a single identifier) |
| `UNMATCHED_ACCOUNT_ENTRY` | No payment lifecycle matched |
| `MISSING_ACCOUNT_EVENT` | Lifecycle accepted but no account event within the window |
| `AMOUNT_MISMATCH` | Amount differs |
| `CURRENCY_MISMATCH` | Currency differs |
| `ACCOUNT_MISMATCH` | Account differs when the account is authoritative |
| `REFERENCE_MISMATCH` | Reference context conflicts |
| `DUPLICATE_ACCOUNT_ENTRY` | Same identity seen twice in the same report type |
| `REVIEW_REQUIRED` | Critical conflict (e.g. debit/credit direction) or identifier conflict |

## Evidence codes

`RECON-UETR-EXACT`, `RECON-TXID-EXACT`, `RECON-E2E-EXACT`, `RECON-INSTR-EXACT`,
`RECON-ACCOUNT-SERVICER-EXACT`, `RECON-AMOUNT-EXACT`, `RECON-CURRENCY-EXACT`,
`RECON-ACCOUNT-EXACT`, `RECON-REFERENCE-NORMALIZED-EXACT`, `RECON-CREDITDEBIT-EXPECTED`.

Conflicts: `RECON-AMOUNT-CONFLICT`, `RECON-CURRENCY-CONFLICT`, `RECON-ACCOUNT-CONFLICT`,
`RECON-ID-CONFLICT`, `RECON-CREDITDEBIT-CONFLICT`.

## Debit/credit direction

`CreditDebitIndicator` is respected. When the account-entry account matches the lifecycle's
debtor account, a `DBIT` is expected; when it matches the creditor account, a `CRDT` is
expected. A mismatch is a critical conflict and routes to review.

## Balances

camt.053 balances are parsed into `AccountBalance` with the codes actually supported
(`OPBD`, `CLBD`, `ITBD`, `AVLB`, `FWAV`). Balances are contextual reporting data, not an
accounting engine.

## camt.054 ↔ camt.053 confirmation

The same account event may appear first in a camt.054 and later in a camt.053. When the
identity matches across report types, PaymentOps records `ACCOUNT_EVENT_CONFIRMED` (status
`RECONCILED`) instead of creating a duplicate lifecycle entry.

## Missing-account-event detection

A payment lifecycle that reaches `ACCEPTED` but has no account event within the configured
window (`DEFAULT_ACCOUNT_WINDOW_HOURS = 48`, configurable via
`POST /api/v1/account-reconciliation/run`) is flagged `MISSING_ACCOUNT_EVENT` and a case is
created. Detection is never immediate. Timestamps are UTC; business-day abstraction is a
placeholder for a later week.

## Out-of-order ingestion

camt first, payment later (or vice versa) is supported. An account entry with no matching
lifecycle is stored as `UNMATCHED_ACCOUNT_ENTRY`; a later payment creates the lifecycle. No
arrival order is required.

## Duplicate handling

Repeated ingestion of the same account event is detected by identity hash. Duplicates are
classified `DUPLICATE_ACCOUNT_ENTRY` and routed to review; nothing is deleted automatically.

## Limitations

- Development subset schemas, not the full official ISO schema packs (see
  `iso20022-schema-provenance.md`).
- Development address geography only (IT, IN, SA, GB, DE, FR, ES, NL); camt messages do not
  trigger address intelligence.
- Reconciliation thresholds/policies are development baselines, not calibrated against
  historical bank data.
- Missing-event detection uses a simple UTC hour window; no banking-SLA/business-day calendar.
