"""Deterministic normalization for matching.

Original source evidence is NEVER mutated. All functions return derived values. Normalization
is policy-independent and deterministic; it exists purely to reduce incidental variation
(whitespace, case, punctuation, Unicode) before exact/fuzzy comparison.

Financial amounts use ``Decimal`` and never floating point.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from matching_engine.models import MatchRecord, NormalizedRecord

# Company/legal-form suffixes normalized to a canonical token (token-aware name matching).
_COMPANY_SUFFIXES: dict[str, str] = {
    "spa": "SPA",
    "s.p.a.": "SPA",
    "s p a": "SPA",
    "srl": "SRL",
    "s.r.l.": "SRL",
    "s r l": "SRL",
    "ltd": "LTD",
    "limited": "LTD",
    "gmbh": "GMBH",
    "inc": "INC",
    "incorporated": "INC",
    "llc": "LLC",
    "l.l.c.": "LLC",
    "bv": "BV",
    "n.v.": "NV",
    "ag": "AG",
}

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^0-9A-Za-zÀ-ÿ ]+")


def _strip(value: str) -> str:
    return value.strip()


def _collapse(value: str) -> str:
    return _WS_RE.sub(" ", value).strip()


def _nfkc(value: str) -> str:
    return unicodedata.normalize("NFKC", value)


def normalize_identifier(value: Any) -> str | None:
    """Uppercase + collapse whitespace. Keeps punctuation (IDs may contain it)."""
    if value is None:
        return None
    s = _collapse(_nfkc(str(value)))
    return s.upper() or None


def normalize_iban(value: Any) -> str | None:
    """IBAN: uppercase, remove spaces and hyphens."""
    if value is None:
        return None
    s = _nfkc(str(value)).replace(" ", "").replace("-", "").replace("\u00a0", "")
    return s.upper() or None


def normalize_bic(value: Any) -> str | None:
    """BIC/SWIFT: uppercase, strip whitespace."""
    if value is None:
        return None
    return _collapse(_nfkc(str(value))).upper() or None


def normalize_reference(value: Any) -> str | None:
    """Reference/invoice number: uppercase, remove spaces, hyphens, dots, and leading '#'."""
    if value is None:
        return None
    s = _nfkc(str(value)).replace(" ", "").replace("-", "").replace(".", "").replace("#", "")
    return s.upper() or None


def _normalize_company_suffix(name: str) -> str:
    """Replace common legal-form spellings with a canonical token, e.g. 'S.P.A.' -> 'SPA'."""
    compact = name.replace(".", " ").replace(",", " ").strip()
    tokens = _collapse(compact).upper().split(" ")
    # Collapse a trailing run of single-letter tokens that form a known suffix (e.g. S P A -> SPA).
    if len(tokens) >= 3 and all(len(t) == 1 for t in tokens[-3:]):
        triple = "".join(tokens[-3:]).lower()
        if triple in _COMPANY_SUFFIXES:
            tokens = tokens[:-3] + [_COMPANY_SUFFIXES[triple]]
    if len(tokens) >= 2 and all(len(t) == 1 for t in tokens[-2:]):
        pair = "".join(tokens[-2:]).lower()
        if pair in _COMPANY_SUFFIXES:
            tokens = tokens[:-2] + [_COMPANY_SUFFIXES[pair]]
    # Normalize single-token variants (SPA, SRL, LTD, GMBH, INC, LLC, BV, NV, AG, LIMITED...).
    tokens = [_COMPANY_SUFFIXES.get(t.lower(), t) for t in tokens]
    return " ".join(tokens)


def normalize_name(value: Any) -> str | None:
    """Name: NFKC, casefold, collapse whitespace, drop punctuation, canonicalize suffix.

    'ACME INDUSTRIA S.P.A.' / 'ACME INDUSTRIA SPA' / 'ACME INDUSTRIA S P A' -> same token set.
    """
    if value is None:
        return None
    s = _collapse(_nfkc(str(value)))
    s = _normalize_company_suffix(s)
    s = _PUNCT_RE.sub(" ", s)
    s = _collapse(s)
    return s.casefold() or None


def normalize_currency(value: Any) -> str | None:
    if value is None:
        return None
    return _collapse(_nfkc(str(value))).upper() or None


def normalize_amount(value: Any) -> Decimal | None:
    """Normalize to a Decimal. Never use float. Returns None for invalid/negative-safe."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        d = Decimal(str(value).replace(",", "").replace(" ", "").strip())
    except (InvalidOperation, ValueError):
        return None
    return d


def normalize_country(value: Any) -> str | None:
    if value is None:
        return None
    return _collapse(_nfkc(str(value))).upper() or None


def normalize_date(value: Any) -> str | None:
    """Normalize a date/datetime to ISO date (YYYY-MM-DD), ignoring timezone."""
    if value is None:
        return None
    if hasattr(value, "strftime"):
        try:
            return cast("str | None", value.strftime("%Y-%m-%d"))
        except ValueError:
            return None
    s = _nfkc(str(value)).strip()
    if not s:
        return None
    # Accept ISO-ish strings; take the date part.
    return s[:10] if len(s) >= 10 else s


def normalize_free_text(value: Any) -> str | None:
    """Free-text descriptor: NFKC + casefold + collapse whitespace."""
    if value is None:
        return None
    return _collapse(_nfkc(str(value))).casefold() or None


# Field -> normalizer mapping used to build a NormalizedRecord.
_NORMALIZERS: dict[str, Any] = {
    "instruction_id": normalize_identifier,
    "end_to_end_id": normalize_identifier,
    "transaction_id": normalize_identifier,
    "debtor_account": normalize_iban,
    "creditor_account": normalize_iban,
    "debtor_agent": normalize_bic,
    "creditor_agent": normalize_bic,
    "remittance_reference": normalize_reference,
    "external_reference": normalize_reference,
    "debtor_name": normalize_name,
    "creditor_name": normalize_name,
    "currency": normalize_currency,
    "amount": normalize_amount,
    "country": normalize_country,
    "booking_date": normalize_date,
    "value_date": normalize_date,
    "message_type": normalize_identifier,
    "source_system": normalize_identifier,
}


def normalize_record(record: MatchRecord) -> NormalizedRecord:
    """Produce a NormalizedRecord; original MatchRecord is untouched."""
    raw: dict[str, Any] = {
        "record_id": record.record_id,
        "record_type": record.record_type.value,
        "organization_id": record.organization_id,
        "instruction_id": record.instruction_id,
        "end_to_end_id": record.end_to_end_id,
        "transaction_id": record.transaction_id,
        "debtor_account": record.debtor_account,
        "creditor_account": record.creditor_account,
        "debtor_agent": record.debtor_agent,
        "creditor_agent": record.creditor_agent,
        "remittance_reference": record.remittance_reference,
        "external_reference": record.external_reference,
        "debtor_name": record.debtor_name,
        "creditor_name": record.creditor_name,
        "currency": record.currency,
        "amount": record.amount,
        "country": record.country,
        "booking_date": record.booking_date,
        "value_date": record.value_date,
        "message_type": record.message_type,
        "source_system": record.source_system,
    }
    values: dict[str, Any] = {}
    for field, raw_value in raw.items():
        if raw_value is None or raw_value == "":
            values[field] = None
            continue
        norm = _NORMALIZERS.get(field)
        values[field] = norm(raw_value) if norm else raw_value
    return NormalizedRecord(
        record_id=record.record_id,
        record_type=record.record_type,
        organization_id=record.organization_id,
        values=values,
        normalized_meta={"normalization_version": "1"},
    )


def amount_abs_diff(a: Decimal | None, b: Decimal | None) -> Decimal | None:
    """Absolute difference between two Decimal amounts (never float)."""
    if a is None or b is None:
        return None
    return abs(a - b)
