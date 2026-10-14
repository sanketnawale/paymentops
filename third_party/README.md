# Third-party vendored components

This directory holds vendored third-party components used by CloudNova PaymentOps.

## swift-address

Vendored, unmodified snapshot of the upstream `Swift-SC/iso20022-address-structuring`
address-structuring engine (town/country inference). See `swift-address/CloudNova-INTEGRATION.md`
and the repository root `THIRD_PARTY.md` for provenance, pinned commit, and license.

## swift-address-resources

Vendored resources for the upstream engine: the trained model (`models/`), reference `misc/`
JSON, and the upstream `LICENSE.txt` / `NOTICES.txt`. See `THIRD_PARTY.md`.

The GeoNames/restCountries-derived reference data is **not** vendored (see `THIRD_PARTY.md`).
It is provisioned at runtime and mounted into the `paymentops-address-structuring` component.
