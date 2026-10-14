"""CloudNova-owned deterministic address normalization.

Performs safe, reversible-in-spirit normalization while never overwriting original values.
The ``PostalAddress.original_fields`` always retains the source; ``normalized_fields`` holds
the derived candidate. No numeric confidence is fabricated; evidence is expressed as
:class:`EvidenceLevel`.
"""

from __future__ import annotations

import unicodedata

from payment_domain.countries import is_valid_country_code, normalize_country_name
from payment_domain.models import EvidenceLevel


def normalize_whitespace(value: str) -> str:
    """Collapse runs of whitespace and strip, without altering letter case."""
    return " ".join(value.split())


def normalize_unicode(value: str) -> str:
    """NFKC normalize (handles full-width, ligatures, etc.) preserving case."""
    return unicodedata.normalize("NFKC", value)


def normalize_country_field(raw: str | None) -> tuple[str | None, EvidenceLevel, str | None]:
    """Normalize a Ctry value to an ISO 3166-1 alpha-2 code.

    Returns ``(code, evidence_level, note)``. A full country name is deterministically mapped
    to its code (HIGH). An already-valid code is returned (HIGH). An unknown value is ``None``.
    """
    if not raw:
        return None, EvidenceLevel.LOW, "no country value"
    cleaned = normalize_whitespace(normalize_unicode(raw)).upper()
    if is_valid_country_code(cleaned):
        return cleaned, EvidenceLevel.HIGH, "valid ISO alpha-2 code"
    code = normalize_country_name(cleaned)
    if code:
        return code, EvidenceLevel.HIGH, f"normalised from name '{raw}'"
    return None, EvidenceLevel.LOW, f"unknown country value '{raw}'"


def extract_country_from_lines(lines: list[str]) -> tuple[str | None, EvidenceLevel]:
    """Try to detect a country (name or code) inside address lines (MEDIUM evidence)."""
    for line in lines:
        for token in _split_commas(line):
            token = normalize_whitespace(normalize_unicode(token))
            if is_valid_country_code(token.upper()):
                return token.upper(), EvidenceLevel.MEDIUM
            code = normalize_country_name(token)
            if code:
                return code, EvidenceLevel.MEDIUM
    return None, EvidenceLevel.LOW


def extract_town_from_lines(
    lines: list[str], country_code: str | None
) -> tuple[str | None, EvidenceLevel]:
    """Conservative, deterministic town extraction from address lines (MEDIUM evidence).

    Heuristic: for a single comma-separated line, the token immediately before the country
    (name or code) is a plausible town. This is deliberately conservative and non-fabricating.
    """
    if not lines:
        return None, EvidenceLevel.LOW
    # Combine lines; look for a token that looks like a town (capitalized, short).
    for line in lines:
        tokens = _split_commas(line)
        for i, token in enumerate(tokens):
            if _is_country_token(token, country_code):
                if i > 0:
                    candidate = tokens[i - 1]
                    if 2 <= len(candidate) <= 35 and candidate[0].isupper():
                        return candidate, EvidenceLevel.MEDIUM
    return None, EvidenceLevel.LOW


def _split_commas(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _is_country_token(token: str, country_code: str | None) -> bool:
    token = normalize_whitespace(token)
    if is_valid_country_code(token.upper()):
        return True
    if normalize_country_name(token):
        return True
    if country_code and token.upper() == country_code:
        return True
    return False
