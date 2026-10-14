# CloudNova integration note

This directory contains a **vendored, unmodified** snapshot of the upstream
`Swift-SC/iso20022-address-structuring` project.

- **Upstream URL:** https://github.com/Swift-SC/iso20022-address-structuring
- **Pinned commit:** `916deca20a2f3501c9b7befb11e21be3931887ba`
- **Upstream version:** `swift_address_structuring` v1.0.2
- **License:** `LICENSE.txt` / `LICENSE.pdf` (Copyright © S.W.I.F.T SC, 2025). See
  `../../../THIRD_PARTY.md`.

## Modifications

**None.** No upstream file has been modified. This is a verbatim snapshot used to build the
separate `paymentops-address-structuring` internal component. The upstream `data_structuring`
package is installed as-is; it is never imported by the core PaymentOps API.

## Usage

The upstream `data_structuring` package is installed into the
`paymentops-address-structuring` image and loaded from a mounted `/resources` volume. The
component exposes an internal HTTP interface; PaymentOps talks to it only via the
`AddressProvider` abstraction.

## Compliance notes

- The Swift name is used here only as upstream attribution/technical identification. CloudNova
  does not brand its product with the Swift name, does not imply endorsement, and does not use
  Swift logos (license §6, §8).
- If any upstream file is ever modified, it must carry a prominent notice describing the change
  (license §7.b) and this note must record it.
