"""CloudNova deterministic address provider.

This is the default provider. It performs deterministic normalization and readiness
classification. It intentionally does NOT pretend to fully structure every postal-address
field; it provides town/country intelligence from explicit source fields and conservative
line-derived heuristics, always preserving original evidence.
"""

from __future__ import annotations

from address_engine.base import AddressAnalysis, AddressProvider
from address_engine.normalization import (
    extract_country_from_lines,
    extract_town_from_lines,
    normalize_whitespace,
)
from address_engine.readiness import classify_readiness
from payment_domain.countries import is_valid_country_code, normalize_country_name
from payment_domain.models import EvidenceLevel, PostalAddress

PROVIDER_NAME = "cloudnova"
PROVIDER_VERSION = "0.1.0"


class CloudNovaAddressProvider(AddressProvider):
    name = PROVIDER_NAME
    version = PROVIDER_VERSION

    def analyze(self, address: PostalAddress) -> AddressAnalysis:
        evidence: list[str] = []

        source_country = address.country
        source_town = normalize_whitespace(address.town_name) if address.town_name else None

        # --- Country resolution ---
        country_code: str | None = None
        country_ok = False
        country_repairable = False
        country_note: str | None = None

        if source_country:
            if is_valid_country_code(source_country):
                country_code = source_country.upper()
                country_ok = True
                country_note = "valid ISO alpha-2 code"
                evidence.append("country is a valid ISO alpha-2 code (HIGH)")
            else:
                code = normalize_country_name(source_country)
                if code:
                    country_code = code
                    country_repairable = True
                    country_note = f"normalised from name '{source_country}'"
                    evidence.append(f"country name '{source_country}' normalised to {code} (HIGH)")
                else:
                    country_note = f"unknown country value '{source_country}'"
                    evidence.append(f"country value '{source_country}' not recognised (LOW)")
        else:
            code, level = extract_country_from_lines(address.address_lines)
            if code:
                country_code = code
                country_repairable = True
                country_note = "derived from address line"
                evidence.append(f"country derived from address line ({level.value})")

        # --- Town resolution ---
        town_name: str | None = None
        town_ok = False
        town_repairable = False
        if source_town:
            town_name = source_town
            town_ok = True
            evidence.append("town present in source (HIGH)")
        else:
            town_name, level = extract_town_from_lines(address.address_lines, country_code)
            if town_name:
                town_repairable = True
                evidence.append(f"town derived from address line ({level.value})")

        readiness = classify_readiness(
            country_ok=country_ok,
            town_ok=town_ok,
            country_repairable=country_repairable,
            town_repairable=town_repairable,
            has_signal=bool(source_country or source_town or address.address_lines),
        )

        normalized_fields: dict[str, str] = {}
        if country_code:
            normalized_fields["country"] = country_code
        if town_name:
            normalized_fields["town_name"] = town_name

        return AddressAnalysis(
            provider=self.name,
            provider_version=self.version,
            country_code=country_code,
            country_name=country_note if country_code and not country_ok else None,
            town_name=town_name,
            normalized_fields=normalized_fields,
            readiness=readiness,
            evidence_level=_overall_level(country_ok, country_repairable, town_ok, town_repairable),
            available=True,
            note=country_note,
            evidence=evidence,
        )


def _overall_level(
    country_ok: bool, country_repairable: bool, town_ok: bool, town_repairable: bool
) -> EvidenceLevel:
    if (country_ok or country_repairable) and (town_ok or town_repairable):
        return EvidenceLevel.HIGH
    if country_ok or country_repairable or town_ok or town_repairable:
        return EvidenceLevel.MEDIUM
    return EvidenceLevel.LOW
