"""Deterministic ISO lifecycle correlation engine.

Answers: "do these ISO messages belong to the same payment lifecycle?"

Uses strong lifecycle identifiers first (message id, original message id, transaction id,
end-to-end id, instruction id, amount+currency, normalized reference). It never uses fuzzy
party names to establish lifecycle correlation. This is SEPARATE from reconciliation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from matching_engine.normalization import normalize_reference
from payment_domain.models import CorrelationStatus, LifecycleStatusReport, PaymentMessage

# Strong identifier evidence codes.
MESSAGE_ID_EXACT = "MESSAGE_ID_EXACT"
ORIGINAL_MESSAGE_ID_EXACT = "ORIGINAL_MESSAGE_ID_EXACT"
TRANSACTION_ID_EXACT = "TRANSACTION_ID_EXACT"
END_TO_END_ID_EXACT = "END_TO_END_ID_EXACT"
INSTRUCTION_ID_EXACT = "INSTRUCTION_ID_EXACT"
AMOUNT_EXACT = "AMOUNT_EXACT"
CURRENCY_EXACT = "CURRENCY_EXACT"
REFERENCE_EXACT = "REFERENCE_EXACT"
ACCOUNT_EXACT = "ACCOUNT_EXACT"
CONFLICT = "IDENTIFIER_CONFLICT"


@dataclass
class CorrelationProfile:
    """Extracted identifiers for lifecycle correlation (never names)."""

    message_id: str | None = None
    original_message_id: str | None = None
    instruction_id: str | None = None
    end_to_end_id: str | None = None
    transaction_id: str | None = None
    amount: int | None = None  # minor units
    currency: str | None = None
    reference: str | None = None
    account: str | None = None
    debtor_account: str | None = None
    creditor_account: str | None = None


@dataclass
class CorrelationResult:
    status: CorrelationStatus
    evidence: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


def profile_from_transaction(tx: Any, *, message_id: str | None) -> CorrelationProfile:
    """Build a correlation profile from a PaymentTransaction."""
    amount = tx.amount
    return CorrelationProfile(
        message_id=message_id,
        instruction_id=tx.instruction_id,
        end_to_end_id=tx.end_to_end_id,
        transaction_id=tx.transaction_id,
        amount=amount.amount_minor if amount else None,
        currency=amount.currency if amount else None,
        reference=(tx.remittance.reference if tx.remittance else None)
        or (
            tx.remittance.unstructured[0] if tx.remittance and tx.remittance.unstructured else None
        ),
        account=(tx.creditor_account.iban if tx.creditor_account else None)
        or (tx.debtor_account.iban if tx.debtor_account else None),
        debtor_account=(tx.debtor_account.iban if tx.debtor_account else None)
        or (tx.debtor_account.other_identification if tx.debtor_account else None),
        creditor_account=(tx.creditor_account.iban if tx.creditor_account else None)
        or (tx.creditor_account.other_identification if tx.creditor_account else None),
    )


def profile_from_status_report(report: LifecycleStatusReport) -> list[CorrelationProfile]:
    """Build correlation profiles for each transaction status in a pacs.002 report."""
    profiles: list[CorrelationProfile] = []
    for tx in report.transaction_statuses:
        amount = tx.amount
        profiles.append(
            CorrelationProfile(
                message_id=report.message_id,
                original_message_id=report.original_message_id,
                instruction_id=tx.original_instruction_id,
                end_to_end_id=tx.original_end_to_end_id,
                transaction_id=tx.original_transaction_id,
                amount=amount.amount_minor if amount else None,
                currency=amount.currency if amount else None,
                reference=tx.reference.end_to_end_id if tx.reference else None,
                account=(tx.reference.transaction_id if tx.reference else None),
            )
        )
    return profiles


def profile_from_message(message: PaymentMessage) -> list[CorrelationProfile]:
    """Build a correlation profile per transaction of a PaymentMessage."""
    return [
        profile_from_transaction(tx, message_id=message.message_id) for tx in message.transactions
    ]


def correlate_profiles(a: CorrelationProfile, b: CorrelationProfile) -> CorrelationResult:
    """Correlate two profiles; returns status + evidence + conflicts (deterministic)."""
    evidence: list[str] = []
    conflicts: list[str] = []

    # Strongest: message-id linkage.
    if a.message_id and b.original_message_id and a.message_id == b.original_message_id:
        evidence.append(ORIGINAL_MESSAGE_ID_EXACT)
    elif a.original_message_id and b.message_id and a.original_message_id == b.message_id:
        evidence.append(ORIGINAL_MESSAGE_ID_EXACT)
    elif a.message_id and b.message_id and a.message_id == b.message_id:
        evidence.append(MESSAGE_ID_EXACT)

    _compare_identifier(
        a.transaction_id,
        b.transaction_id,
        "transaction_id",
        evidence,
        conflicts,
        TRANSACTION_ID_EXACT,
    )
    _compare_identifier(
        a.end_to_end_id, b.end_to_end_id, "end_to_end_id", evidence, conflicts, END_TO_END_ID_EXACT
    )
    _compare_identifier(
        a.instruction_id,
        b.instruction_id,
        "instruction_id",
        evidence,
        conflicts,
        INSTRUCTION_ID_EXACT,
    )

    if (
        a.amount is not None
        and b.amount is not None
        and a.amount == b.amount
        and a.currency
        and b.currency
        and a.currency == b.currency
    ):
        evidence.append(AMOUNT_EXACT)
        evidence.append(CURRENCY_EXACT)

    if a.reference and b.reference:
        ra = normalize_reference(a.reference)
        rb = normalize_reference(b.reference)
        if ra and ra == rb:
            evidence.append(REFERENCE_EXACT)

    if a.account and b.account and a.account.replace(" ", "") == b.account.replace(" ", ""):
        evidence.append(ACCOUNT_EXACT)

    if conflicts:
        status = CorrelationStatus.CONFLICT
    elif any(
        e in evidence for e in (ORIGINAL_MESSAGE_ID_EXACT, MESSAGE_ID_EXACT, TRANSACTION_ID_EXACT)
    ):
        status = CorrelationStatus.CORRELATED
    elif any(e in evidence for e in (END_TO_END_ID_EXACT, INSTRUCTION_ID_EXACT)):
        status = CorrelationStatus.POSSIBLE_CORRELATION
    elif AMOUNT_EXACT in evidence and CURRENCY_EXACT in evidence:
        status = CorrelationStatus.POSSIBLE_CORRELATION
    else:
        status = CorrelationStatus.UNRESOLVED

    return CorrelationResult(status=status, evidence=evidence, conflicts=conflicts)


def _compare_identifier(
    a: Any, b: Any, label: str, evidence: list[str], conflicts: list[str], exact_code: str
) -> None:
    if not a or not b:
        return
    if str(a) == str(b):
        evidence.append(exact_code)
    else:
        conflicts.append(f"{label.upper()}_CONFLICT")
