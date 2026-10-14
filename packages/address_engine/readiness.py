"""Deterministic address-readiness classification (Task 8).

States are evidence-based; we never fabricate a numeric confidence. Classification is based
on the SOURCE state of the address plus whether a reliable candidate can be derived:

- READY          : required structured fields are already valid in the source.
- REPAIRABLE     : a reliable candidate can be derived (e.g. normalizable country).
- REVIEW_REQUIRED: some address data exists but no reliable candidate can be derived.
- UNRESOLVED     : nothing can be determined safely.
"""

from __future__ import annotations

from payment_domain.models import AddressReadiness


def classify_readiness(
    *,
    country_ok: bool,
    town_ok: bool,
    country_repairable: bool,
    town_repairable: bool,
    has_signal: bool,
) -> AddressReadiness:
    if country_ok and town_ok:
        return AddressReadiness.READY
    if country_repairable or town_repairable:
        return AddressReadiness.REPAIRABLE
    if has_signal:
        return AddressReadiness.REVIEW_REQUIRED
    return AddressReadiness.UNRESOLVED
