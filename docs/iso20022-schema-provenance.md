# ISO 20022 Schema Provenance

This document records the provenance, license/redistribution status, and any modifications for
every schema bundled in `schemas/iso20022/`.

## Important

The schemas bundled in this repository are **CloudNova-authored subset XSDs**, not the complete
official ISO 20022 schemas. They model exactly the elements CloudNova PaymentOps supports and
use the **real ISO targetNamespace** so the namespace/version is recognised and validated
explicitly. They are authoritative for the CloudNova supported subset only.

The complete official ISO 20022 XSD sets are large multi-file schemas with restrictive
redistribution terms. They are **not** redistributed inside this repository. Production
substitution of the full official schemas happens under a proper ISO license (see ADR-011) via
an external provisioning step. Validation is never weakened to avoid licensing work.

## Schema inventory

| Message | Version | Source | Retrieval | Checksum (SHA-256 of bundled subset) | License/usage | Bundled | Modifications |
|---------|---------|--------|-----------|--------------------------------------|---------------|---------|---------------|
| pacs.008 | pacs.008.001.08 | CloudNova-authored subset using real ISO namespace | Week 2 | (see file) | CloudNova subset; official schema external | Yes | Subset only, real namespace |
| pain.001 | pain.001.001.13 | CloudNova-authored subset using real ISO namespace | Week 5 | (see file) | CloudNova subset; official schema external | Yes | Subset only, real namespace |
| pacs.002 | pacs.002.001.16 | CloudNova-authored subset using real ISO namespace | Week 5 | (see file) | CloudNova subset; official schema external | Yes | Subset only, real namespace |
| pacs.009 | pacs.009.001.13 | CloudNova-authored subset using real ISO namespace | Week 5 | (see file) | CloudNova subset; official schema external | Yes | Subset only, real namespace |
| camt.053 | camt.053.001.14 | CloudNova-authored subset using real ISO namespace | Week 6 | (see file) | CloudNova subset; official schema external | Yes | Subset only, real namespace |
| camt.054 | camt.054.001.14 | CloudNova-authored subset using real ISO namespace | Week 6 | (see file) | CloudNova subset; official schema external | Yes | Subset only, real namespace |

## camt subset scope

- camt.053.001.14 subset covers: `GrpHdr` (MsgId, CreDtTm), `Stmt` (Id, ElctrncSeqNb, CreDtTm,
  Acct, FrToDt, Bal, Ntry), `Bal` (Tp/CdOrPrtry/Cd, Amt, CdtDbtInd), `Ntry` (NtryRef, Amt,
  CdtDbtInd, Sts, BookgDt, ValDt, AcctSvcrRef, BkTxCd, NtryDtls/TxDtls).
- camt.054.001.14 subset covers: `GrpHdr`, `Ntfctn` (Id, ElctrncSeqNb, CreDtTm, Acct, Ntry),
  and the same `Ntry` structure.
- Neither subset is a full official ISO schema; both use the real ISO targetNamespace.

## Modifications

No bundled schema is an unmodified official ISO schema. Each is a self-contained subset that:
- uses the real ISO `targetNamespace`;
- declares only the elements CloudNova parses;
- is documented in a header comment as a CloudNova subset, never as an official unmodified
  schema.

## External provisioning (production)

The full official ISO 20022 schemas must be provisioned externally (from ISO 20022 or a
licensed vendor) and mounted into `PAYMENTOPS_SCHEMA_DIR`. They are never committed to this
repository. The `IsoMessageRegistry` + `xsd_validator` resolve schemas by version identifier and
are agnostic to whether the mounted schema is the CloudNova subset or the official full set.
