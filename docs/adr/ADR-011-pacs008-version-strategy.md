# ADR-011: Supported pacs.008 version strategy

- **Status:** Accepted
- **Date:** 2026-09-04

## Context

ISO 20022 pacs.008 exists in many versions. Claiming to support every version is not
maintainable and risks silently mis-parsing unknown schemas.

## Decision

- Support an explicit, small set of versions, defined in
  `packages/iso_engine/pacs008/namespace.py`.
- **Week 2 supported version:** `pacs.008.001.08`
  (`urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08`).
- Unsupported pacs.008 versions are rejected with a structured `XML-004` error, never
  silently parsed.
- Non-pacs.008 namespaces are rejected with `XML-004`.

## Schema validation

- The schema is **bundled** under `schemas/iso20022/<version>/<version>.xsd` and versioned
  with the product. No network schema fetching at runtime.
- The bundled XSD is a **self-contained CloudNova subset** that models the fields we parse
  and validate. It is authoritative for the supported subset; the full official ISO schema
  set is substituted under a proper ISO license in production.
- The XML/XSD validator is the authoritative validation source; AI/heuristics never override it.

## Consequences

- Deterministic, explicit version handling.
- Adding a new version requires adding a schema + namespace entry + tests.
- The subset schema intentionally does not validate the entire official message; scope is
  documented.
