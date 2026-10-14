"""Deterministic match explanation codes.

These are stable, machine-readable codes. They are NEVER LLM-generated; LLM text may be added
later only as a human-readable gloss and is never authoritative evidence.
"""

from __future__ import annotations

EXACT = {
    "MATCH-REF-EXACT",
    "MATCH-AMOUNT-EXACT",
    "MATCH-CURRENCY-EXACT",
    "MATCH-IBAN-EXACT",
    "MATCH-BIC-EXACT",
    "MATCH-TXID-EXACT",
    "MATCH-E2E-EXACT",
    "MATCH-COUNTRY-EXACT",
}
SIMILAR = {
    "MATCH-NAME-HIGH-SIMILARITY",
    "MATCH-NAME-MEDIUM-SIMILARITY",
    "MATCH-REF-SIMILARITY",
    "MATCH-DATE-WITHIN-TOLERANCE",
}
CONFLICT = {
    "MATCH-CRITICAL-CURRENCY-CONFLICT",
    "MATCH-CRITICAL-AMOUNT-CONFLICT",
    "MATCH-CRITICAL-TXID-CONFLICT",
    "MATCH-CRITICAL-IBAN-CONFLICT",
}
MISSING = {
    "MATCH-FIELD-MISSING",
}
NOT_APPLICABLE = {
    "MATCH-FIELD-NOT-APPLICABLE",
}
