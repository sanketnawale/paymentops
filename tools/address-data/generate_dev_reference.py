"""Generate a small, reproducible DEVELOPMENT reference dataset for the vendored
address-structuring engine.

This produces files in the EXACT format expected by the upstream ``data_structuring`` code
(see third_party/swift-address). It is a REDUCED corpus used only to prove the real provider
path end-to-end in the dev cluster. It is NOT the production GeoNames/restCountries corpus.

Usage (run in the address-structuring image, which has polars + orjson):
    python generate_dev_reference.py --out /resources

No upstream algorithms are modified. No secrets. Deterministic.
"""

from __future__ import annotations

import argparse
import zlib
from pathlib import Path

import orjson
import polars as pl

# ---------------------------------------------------------------------------
# Test towns (synthetic reference data; NOT real customer data).
# (name, iso, population, cc2)
TOWNS = [
    ("Milano", "IT", 1_400_000, ""),
    ("Roma", "IT", 2_800_000, ""),
    ("Mumbai", "IN", 12_400_000, ""),
    ("New Delhi", "IN", 10_900_000, ""),
    ("Riyadh", "SA", 7_000_000, ""),
    ("London", "GB", 8_900_000, ""),
    ("Berlin", "DE", 3_600_000, ""),
    ("Munchen", "DE", 1_400_000, ""),
    ("Paris", "FR", 2_100_000, ""),
    ("Madrid", "ES", 3_200_000, ""),
    ("Amsterdam", "NL", 900_000, ""),
]

# ISO -> country aliases (names, full names, common variants). Keys are ISO codes.
COUNTRY_ALIASES = {
    "IT": ["ITALIA", "ITALY", "REPUBBLICA ITALIANA"],
    "IN": ["INDIA", "BHARAT"],
    "SA": ["SAUDI ARABIA", "KSA"],
    "GB": ["UNITED KINGDOM", "UK", "GREAT BRITAIN"],
    "DE": ["GERMANY", "DEUTSCHLAND"],
    "FR": ["FRANCE"],
    "ES": ["SPAIN", "ESPANA"],
    "NL": ["NETHERLANDS", "HOLLAND"],
}

# ISO -> province/state aliases.
COUNTRY_PROVINCES = {
    "IT": ["LOMBARDIA", "LAZIO"],
    "IN": ["MAHARASHTRA", "DELHI"],
    "SA": ["RIYADH PROVINCE"],
    "GB": ["GREATER LONDON"],
    "DE": ["BERLIN", "BAVARIA"],
    "FR": ["ILE-DE-FRANCE"],
    "ES": ["COMMUNITY OF MADRID"],
    "NL": ["NORTH HOLLAND"],
}

# ISO -> country specs (domain extensions, postal code regex, phone prefixes).
COUNTRY_SPECS = {
    "IT": {"domain_extensions": [".it"], "postal_code_regex": "", "phone_prefixes": ["+39"]},
    "IN": {"domain_extensions": [".in"], "postal_code_regex": "", "phone_prefixes": ["+91"]},
    "SA": {"domain_extensions": [".sa"], "postal_code_regex": "", "phone_prefixes": ["+966"]},
    "GB": {"domain_extensions": [".uk"], "postal_code_regex": "", "phone_prefixes": ["+44"]},
    "DE": {"domain_extensions": [".de"], "postal_code_regex": "", "phone_prefixes": ["+49"]},
    "FR": {"domain_extensions": [".fr"], "postal_code_regex": "", "phone_prefixes": ["+33"]},
    "ES": {"domain_extensions": [".es"], "postal_code_regex": "", "phone_prefixes": ["+34"]},
    "NL": {"domain_extensions": [".nl"], "postal_code_regex": "", "phone_prefixes": ["+31"]},
}

# Town -> aliases (keys are ASCII-uppercased town names).
TOWN_ALIASES = {
    "MILANO": ["MILANO", "MILAN"],
    "ROMA": ["ROMA", "ROME"],
    "MUMBAI": ["MUMBAI", "BOMBAY"],
    "NEW DELHI": ["NEW DELHI", "DELHI"],
    "RIYADH": ["RIYADH", "RIYAD"],
    "LONDON": ["LONDON", "LONDRES"],
    "BERLIN": ["BERLIN"],
    "MUNCHEN": ["MUNCHEN", "MUNICH"],
    "PARIS": ["PARIS"],
    "MADRID": ["MADRID"],
    "AMSTERDAM": ["AMSTERDAM"],
}


def write_zlib_json(path: Path, obj) -> None:
    path.write_bytes(zlib.compress(orjson.dumps(obj)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="/resources", type=Path)
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    # Towns parquet.
    df = pl.DataFrame(
        {
            "name": [t[0] for t in TOWNS],
            "country code": [t[1] for t in TOWNS],
            "population": [t[2] for t in TOWNS],
        }
    )
    df.write_parquet(out / "towns_all_countries.parquet")

    # Town aliases (zlib JSON).
    write_zlib_json(out / "town_aliases.json", TOWN_ALIASES)

    # Country aliases + province aliases (zlib JSON).
    write_zlib_json(out / "country_names.json", COUNTRY_ALIASES)
    write_zlib_json(out / "country_province_names.json", COUNTRY_PROVINCES)

    # Country specs live under misc/ (upstream config path).
    misc_dir = out / "misc"
    misc_dir.mkdir(parents=True, exist_ok=True)
    write_zlib_json(misc_dir / "country_specs.json", COUNTRY_SPECS)

    # Postcode data (empty dicts/lists are valid; the engine logs counts).
    post_dir = out / "post_codes"
    post_dir.mkdir(parents=True, exist_ok=True)
    for name in [
        "almost_all_countries_dict.json",
        "almost_all_countries_regex_list.json",
        "ireland_dict.json",
        "ireland_regex_list.json",
        "malta_dict.json",
        "malta_regex_list.json",
        "chile_dict.json",
        "chile_regex_list.json",
        "argentina_dict.json",
        "argentina_regex_list.json",
        "brazil_dict.json",
        "brazil_regex_list.json",
        "china_dict.json",
        "china_regex_list.json",
    ]:
        value = {} if name.endswith("_dict.json") else []
        write_zlib_json(post_dir / name, value)

    print(f"Generated dev reference data in {out}")
    print(f"  towns: {len(TOWNS)}, countries: {len(COUNTRY_ALIASES)}")


if __name__ == "__main__":
    main()
