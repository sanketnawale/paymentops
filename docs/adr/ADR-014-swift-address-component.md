# ADR-014: Swift address-provider integration — separate internal component

- **Status:** Accepted
- **Date:** 2026-09-05

## Context

Week 2 created an `AddressProvider` abstraction and a `SwiftDerivedAddressProvider` stub. We
now integrate the **official** upstream address-structuring engine
(`Swift-SC/iso20022-address-structuring`, pinned commit
`916deca20a2f3501c9b7befb11e21be3931887ba`). The upstream is a PyTorch CRF/Transformer model
(torch==2.8.0, polars, safetensors) requiring ~4GB RAM, and it loads a large GeoNames-derived
reference database (towns parquet, country/alias/postcode data).

## Decision

- **Architecture: separate internal component** (Option B). The upstream engine runs in its own
  container `paymentops-address-structuring`, isolated from the core API/worker images.
- **Reason:** torch + polars + model would materially bloat the core API image, increase
  startup time, and reduce failure isolation. A separate component keeps the core API lean and
  lets the heavy inference dependency be scaled/tuned independently.
- The rest of PaymentOps depends only on `AddressProvider`. `SwiftDerivedAddressProvider` is an
  HTTP client that calls the internal component; no Swift-specific import leaks into the API,
  pipeline, rules, repair, or domain model.
- **Resources are loaded from a mounted read-only volume** (`/resources`), not fetched at
  startup. The service `GET /ready` returns ready only when the model and the required
  reference data are present.
- **Reference data provisioning is a deployment concern.** The GeoNames/restCountries-derived
  reference data is large and separately licensed; it is mounted/provisioned at runtime. When
  it is absent, the provider reports not-ready and PaymentOps **falls back** to
  `CloudNovaAddressProvider` without failing the request.

## Consequences

- Core API image stays small (no PyTorch).
- Failure isolation: a Swift component failure/timeout falls back to CloudNova.
- Vendor/licensing: upstream code + model + misc resources are vendored under their licenses;
  reference data (GeoNames/restCountries) is provisioned at runtime under its own licenses.
- Reproducible: pinned upstream commit; no `latest`, no runtime `git clone`.
