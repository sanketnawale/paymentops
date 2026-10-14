# paymentops-address-structuring

Internal-only component that runs the vendored upstream address-structuring engine
(`Swift-SC/iso20022-address-structuring`, pinned commit) for town/country inference.

It is a **separate container** so that the heavy PyTorch/model dependencies do not bloat the
core PaymentOps API/worker images (ADR-014). Only the `paymentops-api` / `paymentops-worker`
may reach it (ClusterIP + NetworkPolicy); it has no public route.

## HTTP interface

- `GET /health` — liveness.
- `GET /ready` — readiness. Returns `not_ready` if the model or the required reference data
  is missing from `/resources`.
- `POST /structure` — body `{ "text": "...", "suggested_country": "IT"?, "force": false }`.
  Returns `{ town, country, town_confidence, country_confidence, town_raw, country_raw,
  suggested_country, force_suggested_country, diagnostics }`. Returns `503` if not ready.

## Resource provisioning

The engine needs a reference database derived from GeoNames/restCountries data
(`towns_all_countries.parquet`, country/alias/postcode JSON) mounted read-only at `/resources`.
This data is large and separately licensed (GeoNames CC BY 4.0, restCountries MPL 2.0, ODbL
share-alike). It is **not** bundled. Until it is mounted, `/ready` reports `not_ready` and
PaymentOps falls back to the deterministic `CloudNovaAddressProvider`.

## Build

```bash
docker build -f apps/address-structuring/Dockerfile -t paymentops-address-structuring:dev .
```

Run locally:

```bash
docker run --rm -p 8000:8000 \
  -v /path/to/resources:/resources:ro \
  paymentops-address-structuring:dev
```
