"""Safe, deterministic transform library for the mapping engine.

Every transform is deterministic, individually tested, fails safely (returns the original
value on error), and never raises. The original source value is preserved in evidence; the
transform produces a normalized candidate.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal, InvalidOperation

from payment_domain.countries import normalize_country_name

TransformFn = Callable[[object], object]
_TRANSFORMS: dict[str, TransformFn] = {}


def transform(name: str, value: object) -> object:
    """Apply a named transform, returning the original value on any failure."""
    fn = _TRANSFORMS.get(name)
    if fn is None:
        return value
    try:
        return fn(value)
    except Exception:  # noqa: BLE001 - transforms fail safely
        return value


def _register(name: str) -> Callable[[TransformFn], TransformFn]:
    def deco(fn: TransformFn) -> TransformFn:
        _TRANSFORMS[name] = fn
        return fn

    return deco


@_register("trim")
def _trim(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


@_register("collapse_whitespace")
def _collapse(value: object) -> object:
    if not isinstance(value, str):
        return value
    return " ".join(value.split())


@_register("upper")
def _upper(value: object) -> object:
    return value.upper() if isinstance(value, str) else value


@_register("lower")
def _lower(value: object) -> object:
    return value.lower() if isinstance(value, str) else value


@_register("normalize_unicode")
def _norm_unicode(value: object) -> object:
    return unicodedata.normalize("NFKC", value) if isinstance(value, str) else value


@_register("remove_safe_punctuation")
def _remove_punct(value: object) -> object:
    if not isinstance(value, str):
        return value
    return re.sub(r"[^A-Za-z0-9\s\-]", "", value)


@_register("country_to_iso2")
def _country_iso2(value: object) -> object:
    if not isinstance(value, str):
        return value
    code = normalize_country_name(value)
    return code if code else value


@_register("parse_decimal")
def _parse_decimal(value: object) -> object:
    if isinstance(value, (int, float, Decimal)):
        return value
    if not isinstance(value, str):
        return value
    try:
        return Decimal(value.strip().replace(",", "."))
    except InvalidOperation:
        return value


@_register("parse_date")
def _parse_date(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if not isinstance(value, str):
        return value
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y%m%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).isoformat()
        except ValueError:
            continue
    return value


@_register("normalize_iban_whitespace")
def _iban_ws(value: object) -> object:
    if not isinstance(value, str):
        return value
    return re.sub(r"\s+", "", value).upper()


@_register("normalize_bic_case")
def _bic_case(value: object) -> object:
    return value.upper() if isinstance(value, str) else value


@_register("company_suffix_normalization")
def _company_suffix(value: object) -> object:
    if not isinstance(value, str):
        return value
    value = value.strip()
    for suffix in ("GmbH", "S.r.l.", "S.p.A.", "Ltd.", "LLC", "Inc.", "PLC"):
        if value.upper().endswith(suffix.upper()):
            return value
    return value


def supported_transforms() -> list[str]:
    return sorted(_TRANSFORMS.keys())
