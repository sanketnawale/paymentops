"""Account-entry identity strategy (Week 6).

Deterministic: strongest identifiers first (UETR, transaction id, end-to-end id, UETR,
instruction id, account servicer reference, normalized reference, amount+currency+date).
Never fuzzy party-name-only.
"""

from __future__ import annotations

from dataclasses import dataclass

from matching_engine.normalization import normalize_reference
from payment_domain.models import AccountEntry, AccountReference


@dataclass
class LifecycleAccountContext:
    """Deterministic account-relevant identifiers of a payment lifecycle."""

    message_id: str | None = None
    original_message_id: str | None = None
    transaction_id: str | None = None
    end_to_end_id: str | None = None
    instruction_id: str | None = None
    uetr: str | None = None
    account_servicer_reference: str | None = None
    reference: str | None = None
    amount_minor: int | None = None
    currency: str | None = None
    debtor_account: str | None = None
    creditor_account: str | None = None


@dataclass
class EntryIdentity:
    """Deterministic identity-key extraction for an account entry."""

    uetr: str | None = None
    transaction_id: str | None = None
    end_to_end_id: str | None = None
    instruction_id: str | None = None
    account_servicer_reference: str | None = None
    entry_reference: str | None = None
    reference: str | None = None
    amount_minor: int | None = None
    currency: str | None = None
    account: str | None = None


def entry_identity(entry: AccountEntry, account: AccountReference | None) -> EntryIdentity:
    amount = entry.amount
    return EntryIdentity(
        uetr=entry.uetr,
        transaction_id=entry.transaction_id,
        end_to_end_id=entry.end_to_end_id,
        instruction_id=entry.instruction_id,
        account_servicer_reference=entry.account_servicer_reference,
        entry_reference=entry.entry_reference,
        reference=entry.remittance_reference,
        amount_minor=amount.amount_minor if amount else None,
        currency=entry.currency or (amount.currency if amount else None),
        account=(account.iban if account else None) or entry.account_servicer_reference,
    )


def normalize_ref(value: str | None) -> str | None:
    return normalize_reference(value)
