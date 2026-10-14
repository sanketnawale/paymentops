# ISO 20022 Support Roadmap

This document records the planned sequence of ISO 20022 message support. It is a **roadmap
only** — later messages are NOT implemented yet and this document must never claim they are.

## Architecture

`iso_engine/registry.py` defines `IsoMessageRegistry`, which maps a fully-qualified message
identifier / namespace to its parser adapter and canonical mapper. The core engine works on the
canonical `PaymentMessage` and is independent of any particular message. Adding a new message
requires registering a new adapter; it does not require changing the core engine.

Each supported message records explicit metadata (`MessageDefinition`):
`message_family`, `message_definition`, `version`, `namespace`, `adapter_version`.

Unsupported versions fail with a clear `UnsupportedMessageError` — never silently parsed.

## Current support

| Message | Version | Status |
|---------|---------|--------|
| pacs.008 | 001.08 | **Supported** (parser + XSD validation + canonical mapper) |
| pain.001 | 001.13 | **Supported** (parser + XSD validation + canonical mapper + lifecycle) |
| pacs.002 | 001.16 | **Supported** (status report parser + XSD validation + lifecycle correlation) |
| pacs.009 | 001.13 | **Supported** (FI-to-FI parser + XSD validation + canonical mapper + lifecycle) |
| camt.053 | 001.14 | **Supported** (statement parser + XSD validation + account entries + reconciliation) |
| camt.054 | 001.14 | **Supported** (notification parser + XSD validation + account entries + reconciliation) |

## Planned sequence (v1)

1. pacs.008 — **done**
2. pain.001 — **done**
3. pacs.002 — **done**
4. pacs.009 — **done**
5. camt.053 — **done**
6. camt.054 — **done**

## Constraints

- Week 6 added camt.053.001.14 and camt.054.001.14. Only these exact versions are supported;
  no family-only dispatch.
- Unsupported versions fail with a structured error, never silently parsed.
- No claim of support for messages not listed under "Current support".
