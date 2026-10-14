"""Candidate retrieval narrowing.

Do NOT compare every record with every record. Build a bounded candidate set using structured
keys: organization, currency, amount range, date window, reference prefix, account. The DB
layer (``matching_service``) translates these criteria into a tenant-scoped SQL query.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from matching_engine.models import MatchingPolicy, MatchRecord
from matching_engine.normalization import normalize_reference

# Hard bounds (development baseline). Never unbounded candidate sets.
DEFAULT_MAX_CANDIDATES = 20
DEFAULT_DATE_WINDOW_DAYS = 7
DEFAULT_AMOUNT_PCT = 20.0


def narrowing_criteria(
    record: MatchRecord,
    policy: MatchingPolicy,
    *,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    date_window_days: int = DEFAULT_DATE_WINDOW_DAYS,
    amount_pct: float = DEFAULT_AMOUNT_PCT,
) -> dict[str, Any]:
    """Return structured narrowing criteria for retrieving candidate records.

    Criteria are deterministic and conservative: they only *narrow*, never drop a possible
    match on insufficient data. Returns an empty-safe dict consumed by the DB layer.
    """
    crit: dict[str, Any] = {
        "organization_id": record.organization_id,
        "record_type": record.record_type.value,
        "max_candidates": max_candidates,
    }

    if record.currency:
        crit["currency"] = record.currency

    if record.amount is not None:
        amount = Decimal(record.amount)
        # Absolute + percentage window; conservative (never floating point).
        tolerance = policy.amount_tolerances.get("amount", amount_pct)
        if tolerance:
            pct = Decimal(str(tolerance)) / Decimal("100")
            crit["amount_min"] = amount - amount * pct
            crit["amount_max"] = amount + amount * pct

    date_fields: list[tuple[str, date]] = []
    if record.booking_date:
        date_fields.append(("booking_date", record.booking_date))
    if record.value_date:
        date_fields.append(("value_date", record.value_date))
    if date_fields:
        crit["date_window_days"] = date_window_days
        crit["date_fields"] = date_fields

    ref = record.remittance_reference or record.external_reference
    if ref:
        norm = normalize_reference(ref)
        crit["reference_prefix"] = norm[:8] if norm else None

    account = record.debtor_account or record.creditor_account
    if account:
        crit["account"] = account

    return crit
