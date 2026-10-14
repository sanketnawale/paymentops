"""Swift-derived address provider — HTTP client to the internal component.

The rest of PaymentOps depends only on :class:`AddressProvider`. This client calls the
separately-containerized ``paymentops-address-structuring`` service (which runs the vendored
upstream engine). It never imports upstream ``data_structuring`` directly.

Behavior:
- Strict timeout, bounded retries (no infinite loop), and a simple circuit breaker.
- If the service is unavailable / not-ready / times out / errors, ``analyze`` returns an
  ``AddressAnalysis`` with ``available=False`` and ``note="ADDRESS_PROVIDER_FALLBACK"`` so the
  caller (FallbackAddressProvider) can fall back to CloudNova.
- Never leaks internal details; never logs the raw address.

Country suggestion: the caller may pass a suggested country (soft) and, when justified, force
(hard) via ``force_suggested_country``.
"""

from __future__ import annotations

import time
from typing import cast

import httpx

from address_engine.base import AddressAnalysis, AddressProvider
from payment_domain.countries import is_valid_country_code
from payment_domain.models import AddressReadiness, EvidenceLevel, PostalAddress

PROVIDER_NAME = "swift_derived"
PROVIDER_VERSION = "0.1.0"  # CloudNova adapter version
# Pinned upstream commit/version of the vendored engine.
UPSTREAM_COMMIT = "916deca20a2f3501c9b7befb11e21be3931887ba"
UPSTREAM_VERSION = "1.0.2"

FALLBACK_NOTE = "ADDRESS_PROVIDER_FALLBACK"


class SwiftDerivedAddressProvider(AddressProvider):
    name = PROVIDER_NAME
    version = PROVIDER_VERSION

    def __init__(
        self,
        endpoint_url: str,
        *,
        timeout_seconds: float = 2.0,
        max_retries: int = 1,
        circuit_threshold: int = 3,
        circuit_cooldown_seconds: float = 30.0,
    ) -> None:
        self._endpoint = endpoint_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._circuit_threshold = circuit_threshold
        self._cooldown = circuit_cooldown_seconds
        self._failures = 0
        self._circuit_open_until = 0.0

    @property
    def configured(self) -> bool:
        return bool(self._endpoint)

    @property
    def description(self) -> str:
        return f"{self.name} (adapter v{self.version}, upstream {UPSTREAM_COMMIT[:12]})"

    def _circuit_open(self) -> bool:
        return time.monotonic() < self._circuit_open_until

    def _record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._circuit_threshold:
            self._circuit_open_until = time.monotonic() + self._cooldown
            self._failures = 0

    def _record_success(self) -> None:
        self._failures = 0

    def analyze(self, address: PostalAddress) -> AddressAnalysis:
        if not self.configured or self._circuit_open():
            return self._unavailable("not configured or circuit open")

        lines = self._address_lines(address)
        if not lines:
            return self._unavailable("no address lines to structure")

        suggested_country, force = self._suggestion(address)

        payload: dict[str, object] = {
            "text": "\n".join(lines),
            "suggested_country": suggested_country,
            "force": force,
        }
        try:
            result = self._post("/structure", payload)
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError):
            self._record_failure()
            return self._unavailable("provider call failed or timed out")

        self._record_success()
        return self._build_analysis(result, address, suggested_country, force)

    def _post(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        url = f"{self._endpoint}{path}"
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    resp = client.post(url, json=payload)
                resp.raise_for_status()
                return cast(dict[str, object], resp.json())
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    time.sleep(0.1 * (attempt + 1))
        raise last_exc or httpx.TransportError("provider request failed")

    def _build_analysis(
        self,
        result: dict[str, object],
        address: PostalAddress,
        suggested_country: str | None,
        force: bool,
    ) -> AddressAnalysis:
        country = result.get("country")
        town = result.get("town")
        country_conf = result.get("country_confidence")
        town_conf = result.get("town_confidence")
        evidence = ["upstream town/country inference", f"upstream commit {UPSTREAM_COMMIT[:12]}"]
        readiness = self._classify(town, country, country_conf, town_conf)
        normalized: dict[str, str] = {}
        if country:
            normalized["country"] = str(country)
        if town:
            normalized["town_name"] = str(town)
        return AddressAnalysis(
            provider=self.name,
            provider_version=self.version,
            country_code=str(country) if country else None,
            country_name=None,
            town_name=str(town) if town else None,
            normalized_fields=normalized,
            readiness=readiness,
            evidence_level=_level(country_conf, town_conf),
            available=True,
            note="upstream engine",
            evidence=evidence,
        )

    def _classify(
        self,
        town: object,
        country: object,
        country_conf: object,
        town_conf: object,
    ) -> AddressReadiness:
        if (
            country
            and town
            and isinstance(country_conf, float)
            and isinstance(town_conf, float)
            and country_conf >= 0.15
            and town_conf >= 0.15
        ):
            return AddressReadiness.READY
        if country or town:
            return AddressReadiness.REVIEW_REQUIRED
        return AddressReadiness.UNRESOLVED

    def _unavailable(self, reason: str) -> AddressAnalysis:
        return AddressAnalysis(
            provider=self.name,
            provider_version=self.version,
            readiness=AddressReadiness.UNRESOLVED,
            evidence_level=EvidenceLevel.LOW,
            available=False,
            note=FALLBACK_NOTE,
            evidence=[reason],
        )

    def _address_lines(self, address: PostalAddress) -> list[str]:
        lines = list(address.address_lines)
        # Fall back to composing structured fields if no AdrLine present.
        if not lines:
            parts = [
                p
                for p in (
                    address.street_name,
                    address.building_number,
                    address.postcode,
                    address.town_name,
                    address.country,
                )
                if p
            ]
            if parts:
                lines = [" ".join(parts)]
        return lines

    def _suggestion(self, address: PostalAddress) -> tuple[str | None, bool]:
        """Return (suggested_country, force) based on source context.

        Soft suggestion: pass the country as a hint. Hard suggestion (force) is used only when
        the country is a valid ISO alpha-2 code from structured source (justified context).
        """
        if address.country and is_valid_country_code(address.country):
            return address.country, True
        if address.country:
            return address.country, False
        return None, False


def _level(country_conf: object, town_conf: object) -> EvidenceLevel:
    if (
        isinstance(country_conf, float)
        and country_conf >= 0.5
        and isinstance(town_conf, float)
        and town_conf >= 0.5
    ):
        return EvidenceLevel.HIGH
    if isinstance(country_conf, float) or isinstance(town_conf, float):
        return EvidenceLevel.MEDIUM
    return EvidenceLevel.LOW
