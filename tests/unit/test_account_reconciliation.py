"""Deterministic account-entry reconciliation engine tests."""

from __future__ import annotations

from iso_engine.account.identity import LifecycleAccountContext
from iso_engine.account.reconciliation import (
    RECON_AMOUNT_CONFLICT,
    RECON_AMOUNT_EXACT,
    RECON_CURRENCY_EXACT,
    RECON_E2E_EXACT,
    reconcile_account_entry,
)
from payment_domain.models import (
    AccountEntry,
    AccountReconciliationStatus,
    AccountReference,
    CreditDebitIndicator,
    MonetaryAmount,
)

ACCOUNT = AccountReference(iban="IT60X0542811101000000123456", currency="EUR")
CONTEXT = LifecycleAccountContext(
    transaction_id="TX-0001",
    end_to_end_id="E2E-0001",
    instruction_id="INSTR-0001",
    amount_minor=1250000,
    currency="EUR",
    debtor_account="IT60X0542811101000000123456",
    creditor_account="DE89370400440532013000",
)


def _entry(**kw) -> AccountEntry:
    base = {
        "end_to_end_id": "E2E-0001",
        "instruction_id": "INSTR-0001",
        "transaction_id": "TX-0001",
        "amount": MonetaryAmount(amount_minor=1250000, currency="EUR"),
        "currency": "EUR",
        "credit_debit": CreditDebitIndicator.DBIT,
    }
    base.update(kw)
    return AccountEntry(**base)


def test_reconciled_exact_identifiers():
    result = reconcile_account_entry(_entry(), ACCOUNT, CONTEXT)
    assert result.classification == AccountReconciliationStatus.RECONCILED
    assert RECON_E2E_EXACT in result.evidence
    assert RECON_AMOUNT_EXACT in result.evidence
    assert RECON_CURRENCY_EXACT in result.evidence
    assert result.match_score > 0


def test_amount_mismatch_not_reconciled():
    entry = _entry(amount=MonetaryAmount(amount_minor=1200000, currency="EUR"))
    result = reconcile_account_entry(entry, ACCOUNT, CONTEXT)
    assert result.classification == AccountReconciliationStatus.AMOUNT_MISMATCH
    assert RECON_AMOUNT_CONFLICT in result.conflicts


def test_currency_mismatch_not_reconciled():
    entry = _entry(amount=MonetaryAmount(amount_minor=1250000, currency="USD"), currency="USD")
    result = reconcile_account_entry(entry, ACCOUNT, CONTEXT)
    assert result.classification == AccountReconciliationStatus.CURRENCY_MISMATCH


def test_account_mismatch():
    other = AccountReference(iban="GB33BUKB20201555555555", currency="EUR")
    entry = _entry()
    result = reconcile_account_entry(entry, other, CONTEXT)
    assert result.classification == AccountReconciliationStatus.ACCOUNT_MISMATCH


def test_credit_debit_direction_conflict():
    # Debtor account expected DBIT; a CRDT on the debtor account is a conflict.
    entry = _entry(credit_debit=CreditDebitIndicator.CRDT)
    result = reconcile_account_entry(entry, ACCOUNT, CONTEXT)
    assert result.classification == AccountReconciliationStatus.REVIEW_REQUIRED
    assert any("CREDITDEBIT" in c for c in result.conflicts)


def test_unmatched_no_identifiers():
    entry = AccountEntry(
        amount=MonetaryAmount(amount_minor=999, currency="USD"),
        currency="USD",
        credit_debit=CreditDebitIndicator.CRDT,
    )
    result = reconcile_account_entry(entry, None, LifecycleAccountContext())
    assert result.classification == AccountReconciliationStatus.UNMATCHED_ACCOUNT_ENTRY


def test_possible_reconciliation_amount_currency_only():
    entry = _entry(end_to_end_id=None, instruction_id=None, transaction_id=None)
    result = reconcile_account_entry(entry, ACCOUNT, CONTEXT)
    assert result.classification == AccountReconciliationStatus.POSSIBLE_RECONCILIATION
