# Address reference data tooling

Reproducible generation of the **DEVELOPMENT** reference dataset for the vendored
address-structuring engine (`paymentops-address-structuring`).

## `generate_dev_reference.py`

Generates the files in the exact format expected by the upstream `data_structuring` engine:

- `towns_all_countries.parquet` — towns (name, country code, population).
- `town_aliases.json`, `country_names.json`, `country_province_names.json` — zlib-compressed
  JSON alias dictionaries.
- `misc/country_specs.json` — zlib-compressed country specs.
- `post_codes/*.json` — (empty) postcode dicts/regex lists.

The model (`models/`) and `misc/country_city_same_name.json` / `misc/country_groupings_*.json`
are copied from the vendored resources repo (`third_party/swift-address-resources`).

The build is **deterministic** (fixed data, no external downloads, no secrets). It is run in the
`paymentops-address-structuring` image build and bundled at `/bundled-resources`, then seeded
into the reference-data PVC by an initContainer.

> **This is a DEVELOPMENT dataset, NOT the production GeoNames/restCountries reference corpus.**
> Production reference data must be generated from the external datasets (GeoNames CC BY 4.0,
> restCountries MPL 2.0, etc.) and mounted at `/resources`; see `../../THIRD_PARTY.md`.

## Run

```bash
# In the address-structuring image (has polars + orjson):
python tools/address-data/generate_dev_reference.py --out /resources
```
