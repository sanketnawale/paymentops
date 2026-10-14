# ADR-012: Swift address-provider isolation

- **Status:** Accepted
- **Date:** 2026-09-04

## Context

We reuse the open-source Swift Hybrid Postal Address Structuring model for town/country
intelligence. It is a PyTorch CRF model requiring ~4GB RAM, plus separately-downloaded model
resources and GeoNames data. Bringing it into the core API image would make it huge and
couple PaymentOps to Swift internals.

## Decision

- Introduce an `AddressProvider` interface (`packages/address_engine/base.py`). The rest of
  PaymentOps depends only on `AddressProvider`, never on Swift-specific types.
- Providers: `CloudNovaAddressProvider` (deterministic default), `SwiftDerivedAddressProvider`
  (isolated adapter), future `CustomerProvidedAddressProvider`.
- **The Swift model runs as a separately-containerized internal component** (option B), not
  in-process in the API. The `SwiftDerivedAddressProvider` is a thin adapter that targets that
  service. In Week 2 the Swift component is NOT vendored/deployed; the adapter reports
  `available=False` and the pipeline falls back to the CloudNova deterministic provider.
- The Swift provider provides **town and country intelligence only**; it does not fully
  structure every postal-address field.

## Legal / attribution

- Keep the upstream component isolated; preserve license/copyright notices.
- Mark modified upstream files; maintain a CHANGES/NOTICE file (`THIRD_PARTY.md`).
- Do not use the Swift name in CloudNova product branding; do not imply endorsement; no Swift
  logos.
- Verify the separately-downloaded model resources and GeoNames data licenses before
  redistributing them (GeoNames is CC-BY and requires attribution).

## Consequences

- API image stays lean (no PyTorch).
- Clean provider boundary; swapping in the Swift component or a customer provider later is
  config-only.
- Week 2 demo uses deterministic CloudNova town/country intelligence; Swift is designed-in
  but not enabled.
