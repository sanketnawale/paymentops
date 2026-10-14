"""Deterministic account-entry reconciliation against payment lifecycles.

This is financial/account reconciliation, NOT ISO lifecycle correlation. It decides whether an
account movement (camt.053/camt.054) corresponds to a payment lifecycle, and classifies the
outcome. Critical conflicts prevent unsafe auto-reconciliation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from iso_engine.account.identity import (
    LifecycleAccountContext,
    entry_identity,
    normalize_ref,
)
from payment_domain.models import (
    AccountEntry,
    AccountReconciliationStatus,
    AccountReference,
    CreditDebitIndicator,
)

# Evidence codes.
RECON_UETR_EXACT = "RECON-UETR-EXACT"
RECON_TXID_EXACT = "RECON-TXID-EXACT"
RECON_E2E_EXACT = "RECON-E2E-EXACT"
RECON_INSTR_EXACT = "RECON-INSTR-EXACT"
RECON_ACCOUNT_SERVICER_EXACT = "RECON-ACCOUNT-SERVICER-EXACT"
RECON_AMOUNT_EXACT = "RECON-AMOUNT-EXACT"
RECON_CURRENCY_EXACT = "RECON-CURRENCY-EXACT"
RECON_DATE_WITHIN_TOLERANCE = "RECON-DATE-WITHIN-TOLERANCE"
RECON_ACCOUNT_EXACT = "RECON-ACCOUNT-EXACT"
RECON_REFERENCE_NORMALIZED_EXACT = "RECON-REFERENCE-NORMALIZED-EXACT"
RECON_CREDIT_DEBIT_EXPECTED = "RECON-CREDITDEBIT-EXPECTED"

# Conflict codes.
RECON_AMOUNT_CONFLICT = "RECON-AMOUNT-CONFLICT"
RECON_CURRENCY_CONFLICT = "RECON-CURRENCY-CONFLICT"
RECON_ACCOUNT_CONFLICT = "RECON-ACCOUNT-CONFLICT"
RECON_ID_CONFLICT = "RECON-ID-CONFLICT"
RECON_CREDIT_DEBIT_CONFLICT = "RECON-CREDITDEBIT-CONFLICT"

_STRONG_EXACT = {RECON_UETR_EXACT, RECON_TXID_EXACT, RECON_E2E_EXACT, RECON_INSTR_EXACT}
_CRITICAL_CONFLICTS = {
    RECON_AMOUNT_CONFLICT,
    RECON_CURRENCY_CONFLICT,
    RECON_ACCOUNT_CONFLICT,
    RECON_CREDIT_DEBIT_CONFLICT,
}


@dataclass
class AccountReconciliationResult:
    classification: AccountReconciliationStatus
    evidence: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    match_score: float = 0.0


def reconcile_account_entry(
    entry: AccountEntry,
    account: AccountReference | None,
    lifecycle: LifecycleAccountContext,
) -> AccountReconciliationResult:
    """Deterministically reconcile one account entry against a payment lifecycle context."""
    ident = entry_identity(entry, account)
    evidence: list[str] = []
    conflicts: list[str] = []

    # --- Identifier hierarchy (strongest first) ---
    _compare(ident.uetr, lifecycle.uetr, RECON_UETR_EXACT, "uetr", evidence, conflicts)
    _compare(
        ident.transaction_id,
        lifecycle.transaction_id,
        RECON_TXID_EXACT,
        "txid",
        evidence,
        conflicts,
    )
    _compare(
        ident.end_to_end_id, lifecycle.end_to_end_id, RECON_E2E_EXACT, "e2e", evidence, conflicts
    )
    _compare(
        ident.instruction_id,
        lifecycle.instruction_id,
        RECON_INSTR_EXACT,
        "instr",
        evidence,
        conflicts,
    )
    _compare(
        ident.account_servicer_reference,
        lifecycle.account_servicer_reference,
        RECON_ACCOUNT_SERVICER_EXACT,
        "servicer",
        evidence,
        conflicts,
    )

    # --- Amount + currency ---
    if ident.amount_minor is not None and lifecycle.amount_minor is not None:
        if ident.amount_minor == lifecycle.amount_minor:
            evidence.append(RECON_AMOUNT_EXACT)
        else:
            conflicts.append(RECON_AMOUNT_CONFLICT)

    entry_ccy = ident.currency
    if entry_ccy and lifecycle.currency:
        if entry_ccy.upper() == lifecycle.currency.upper():
            evidence.append(RECON_CURRENCY_EXACT)
        else:
            conflicts.append(RECON_CURRENCY_CONFLICT)

    # --- Account context + debit/credit direction ---
    entry_account = (account.iban if account else None) or (
        account.other_identification if account else None
    )
    expected_direction = _expected_direction(entry_account, lifecycle)
    if (
        entry_account
        and lifecycle.creditor_account
        and _same_account(entry_account, lifecycle.creditor_account)
    ):
        evidence.append(RECON_ACCOUNT_EXACT)
    if (
        entry_account
        and lifecycle.debtor_account
        and _same_account(entry_account, lifecycle.debtor_account)
    ):
        evidence.append(RECON_ACCOUNT_EXACT)
    if expected_direction is not None and entry.credit_debit is not None:
        if entry.credit_debit == expected_direction:
            evidence.append(RECON_CREDIT_DEBIT_EXPECTED)
        else:
            conflicts.append(RECON_CREDIT_DEBIT_CONFLICT)
    elif entry_account and lifecycle.creditor_account and lifecycle.debtor_account:
        # Account is known but does not match either lifecycle account.
        if not _same_account(entry_account, lifecycle.creditor_account) and not _same_account(
            entry_account, lifecycle.debtor_account
        ):
            conflicts.append(RECON_ACCOUNT_CONFLICT)

    # --- Normalized reference ---
    if ident.reference and lifecycle.reference:
        if normalize_ref(ident.reference) == normalize_ref(lifecycle.reference):
            evidence.append(RECON_REFERENCE_NORMALIZED_EXACT)

    score = _score(evidence)
    classification = _classify(evidence, conflicts, score)
    return AccountReconciliationResult(
        classification=classification,
        evidence=evidence,
        conflicts=conflicts,
        match_score=score,
    )


def _compare(
    a: str | None,
    b: str | None,
    code: str,
    label: str,
    evidence: list[str],
    conflicts: list[str],
) -> None:
    if not a or not b:
        return
    if a.strip().upper() == b.strip().upper():
        evidence.append(code)
    else:
        conflicts.append(RECON_ID_CONFLICT)


def _same_account(a: str, b: str) -> bool:
    return (
        a.replace(" ", "").replace("-", "").upper() == b.replace(" ", "").replace("-", "").upper()
    )


def _expected_direction(
    entry_account: str | None, lifecycle: LifecycleAccountContext
) -> CreditDebitIndicator | None:
    if not entry_account:
        return None
    if lifecycle.creditor_account and _same_account(entry_account, lifecycle.creditor_account):
        return CreditDebitIndicator.CRDT
    if lifecycle.debtor_account and _same_account(entry_account, lifecycle.debtor_account):
        return CreditDebitIndicator.DBIT
    return None


def _score(evidence: list[str]) -> float:
    """Deterministic 0..100 score from weighted evidence (not a probability)."""
    weights = {
        RECON_UETR_EXACT: 40,
        RECON_TXID_EXACT: 40,
        RECON_E2E_EXACT: 30,
        RECON_INSTR_EXACT: 20,
        RECON_ACCOUNT_SERVICER_EXACT: 20,
        RECON_ACCOUNT_EXACT: 15,
        RECON_AMOUNT_EXACT: 20,
        RECON_CURRENCY_EXACT: 10,
        RECON_REFERENCE_NORMALIZED_EXACT: 15,
        RECON_CREDIT_DEBIT_EXPECTED: 5,
    }
    total = sum(weights.values())
    got = sum(weights.get(code, 0) for code in evidence)
    return round(100.0 * got / total, 2) if total else 0.0


def _classify(
    evidence: list[str], conflicts: list[str], score: float
) -> AccountReconciliationStatus:
    has_strong = any(e in _STRONG_EXACT for e in evidence)
    has_amount = RECON_AMOUNT_EXACT in evidence
    has_currency = RECON_CURRENCY_EXACT in evidence

    # Critical conflicts never auto-reconcile.
    if conflicts:
        if RECON_CURRENCY_CONFLICT in conflicts:
            return AccountReconciliationStatus.CURRENCY_MISMATCH
        if RECON_AMOUNT_CONFLICT in conflicts:
            return AccountReconciliationStatus.AMOUNT_MISMATCH
        if RECON_ACCOUNT_CONFLICT in conflicts:
            return AccountReconciliationStatus.ACCOUNT_MISMATCH
        if RECON_CREDIT_DEBIT_CONFLICT in conflicts or RECON_ID_CONFLICT in conflicts:
            return AccountReconciliationStatus.REVIEW_REQUIRED

    if has_strong and has_amount and has_currency:
        return AccountReconciliationStatus.RECONCILED
    if has_strong and (has_amount or has_currency):
        return AccountReconciliationStatus.POSSIBLE_RECONCILIATION
    if has_amount and has_currency:
        return AccountReconciliationStatus.POSSIBLE_RECONCILIATION
    if has_strong:
        return AccountReconciliationStatus.POSSIBLE_RECONCILIATION
    return AccountReconciliationStatus.UNMATCHED_ACCOUNT_ENTRY
