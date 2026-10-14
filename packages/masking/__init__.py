"""Field masking/redaction package.

Responsibility (planned): deterministic, reversible-where-required masking of IBAN/account/
name/address fields for safe display, logging, and audit. This is defence-in-depth.
Provides an immediate helper used by the API to sanitize data before logging.
"""

from __future__ import annotations


def mask_iban(value: str) -> str:
    """Mask an IBAN for display, keeping the first 4 and last 4 characters."""
    if not value or len(value) < 8:
        return "[REDACTED]"
    return f"{value[:4]}...{value[-4:]}"


def mask_account(value: str) -> str:
    """Mask an account number for display."""
    if not value:
        return "[REDACTED]"
    if len(value) <= 4:
        return "*" * len(value)
    return f"{'*' * (len(value) - 4)}{value[-4:]}"
