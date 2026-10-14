"""Fallback address provider policy.

Wraps a primary provider (e.g. Swift-derived) and a fallback (CloudNova deterministic). If
the primary is unavailable (not configured, not-ready, timeout, error, circuit open), it
returns the fallback result with ``fallback=True`` and a safe ``ADDRESS_PROVIDER_FALLBACK``
note. The rest of PaymentOps only sees an :class:`AddressProvider`.
"""

from __future__ import annotations

from dataclasses import replace

from address_engine.base import AddressAnalysis, AddressProvider
from payment_domain.models import PostalAddress

FALLBACK_NOTE = "ADDRESS_PROVIDER_FALLBACK"


class FallbackAddressProvider(AddressProvider):
    name = "fallback"
    version = "0.1.0"

    def __init__(self, primary: AddressProvider, fallback: AddressProvider) -> None:
        self._primary = primary
        self._fallback = fallback
        self._fallbacks = 0

    @property
    def fallback_count(self) -> int:
        return self._fallbacks

    def analyze(self, address: PostalAddress) -> AddressAnalysis:
        primary_result = self._primary.analyze(address)
        if primary_result.available:
            return primary_result
        self._fallbacks += 1
        fallback_result = self._fallback.analyze(address)
        # Mark the fallback on the deterministic result; never expose primary internals.
        return replace(
            fallback_result,
            fallback=True,
            note=FALLBACK_NOTE,
            evidence=[
                *fallback_result.evidence,
                "primary provider unavailable; CloudNova fallback",
            ],
        )
