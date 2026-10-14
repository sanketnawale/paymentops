"""ISO 3166-1 alpha-2 country reference data.

Deterministic, minimal, and used for country-code validation (ADR-003) and country-name
normalization. This is a curated subset sufficient for Week 2 fixtures; it is not a full
commercial dataset. Original source values are never overwritten.
"""

from __future__ import annotations

# ISO 3166-1 alpha-2 codes we treat as valid (curated subset).
VALID_COUNTRY_CODES: frozenset[str] = frozenset(
    {
        "AD",
        "AE",
        "AR",
        "AT",
        "AU",
        "BE",
        "BG",
        "BR",
        "CA",
        "CH",
        "CN",
        "CY",
        "CZ",
        "DE",
        "DK",
        "EE",
        "ES",
        "FI",
        "FR",
        "GB",
        "GR",
        "HR",
        "HU",
        "IE",
        "IL",
        "IN",
        "IS",
        "IT",
        "JP",
        "KR",
        "LI",
        "LT",
        "LU",
        "LV",
        "MC",
        "MT",
        "MX",
        "NL",
        "NO",
        "NZ",
        "PL",
        "PT",
        "RO",
        "RS",
        "RU",
        "SE",
        "SI",
        "SK",
        "SM",
        "TR",
        "UA",
        "US",
        "ZA",
    }
)

# Common country names (uppercase, stripped) mapped to their ISO alpha-2 code.
COUNTRY_NAME_TO_CODE: dict[str, str] = {
    "AUSTRIA": "AT",
    "BELGIUM": "BE",
    "BULGARIA": "BG",
    "BRAZIL": "BR",
    "CANADA": "CA",
    "SWITZERLAND": "CH",
    "CHINA": "CN",
    "CYPRUS": "CY",
    "CZECHIA": "CZ",
    "CZECH REPUBLIC": "CZ",
    "GERMANY": "DE",
    "DENMARK": "DK",
    "ESTONIA": "EE",
    "SPAIN": "ES",
    "FINLAND": "FI",
    "FRANCE": "FR",
    "UNITED KINGDOM": "GB",
    "GREECE": "GR",
    "CROATIA": "HR",
    "HUNGARY": "HU",
    "IRELAND": "IE",
    "ISRAEL": "IL",
    "INDIA": "IN",
    "ICELAND": "IS",
    "ITALY": "IT",
    "JAPAN": "JP",
    "LIECHTENSTEIN": "LI",
    "LITHUANIA": "LT",
    "LUXEMBOURG": "LU",
    "LATVIA": "LV",
    "MONACO": "MC",
    "MALTA": "MT",
    "MEXICO": "MX",
    "NETHERLANDS": "NL",
    "NORWAY": "NO",
    "NEW ZEALAND": "NZ",
    "POLAND": "PL",
    "PORTUGAL": "PT",
    "ROMANIA": "RO",
    "SERBIA": "RS",
    "RUSSIA": "RU",
    "SWEDEN": "SE",
    "SLOVENIA": "SI",
    "SLOVAKIA": "SK",
    "SAN MARINO": "SM",
    "TURKEY": "TR",
    "UKRAINE": "UA",
    "UNITED STATES": "US",
    "UNITED STATES OF AMERICA": "US",
    "SOUTH AFRICA": "ZA",
}


def is_valid_country_code(code: str) -> bool:
    return code in VALID_COUNTRY_CODES


def normalize_country_name(name: str) -> str | None:
    """Return the ISO alpha-2 code for a country name, or ``None`` if unknown."""
    key = name.strip().upper()
    return COUNTRY_NAME_TO_CODE.get(key)
