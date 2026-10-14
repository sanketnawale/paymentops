"""Account-reporting performance baseline (Week 6, Task 46).

DEVELOPMENT BASELINE only — local hardware, not a production-scale claim.

Run: python tools/account_benchmark.py
"""

from __future__ import annotations

import statistics
import time
from pathlib import Path

from address_engine.providers import CloudNovaAddressProvider
from analysis.pipeline import AnalysisPipeline
from iso_engine import build_default_registry
from iso_engine.account.identity import LifecycleAccountContext
from iso_engine.account.reconciliation import reconcile_account_entry
from iso_engine.xml_security import secure_parse
from iso_engine.xsd_validator import validate_message
from payment_domain.models import (
    AccountEntry,
    AccountReference,
    CreditDebitIndicator,
    MonetaryAmount,
)
from rules_engine import build_address_ruleset

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "iso"
REG = build_default_registry()
PIPELINE = AnalysisPipeline(
    address_provider=CloudNovaAddressProvider(), rules_engine=build_address_ruleset()
)


def _stats(lat: list[float]) -> str:
    return f"p50={statistics.median(lat):.3f}ms p95={sorted(lat)[int(len(lat) * 0.95) - 1]:.3f}ms"


def _timed(fn, n: int) -> list[float]:
    out = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t0) * 1000)
    return out


def _camt054(entries: int) -> bytes:
    rows = "".join(
        f'<Ntry><NtryRef>N{i}</NtryRef><Amt Ccy="EUR">10.00</Amt><CdtDbtInd>DBIT</CdtDbtInd>'
        f"<BookgDt><Dt>2026-01-12</Dt></BookgDt>"
        f"<NtryDtls><TxDtls><Refs><EndToEndId>E{i}</EndToEndId><TxId>T{i}</TxId></Refs>"
        f"</TxDtls></NtryDtls></Ntry>"
        for i in range(entries)
    )
    return (
        '<?xml version="1.0"?>'
        '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.054.001.14">'
        "<BkToCstmrDbtCdtNtfctn><GrpHdr><MsgId>M</MsgId>"
        "<CreDtTm>2026-01-12T10:00:00Z</CreDtTm></GrpHdr>"
        f"<Ntfctn><Id>N</Id>{rows}</Ntfctn></BkToCstmrDbtCdtNtfctn></Document>"
    ).encode()


def main() -> None:
    for n in (1, 100):
        data = _camt054(n)
        lat = _timed(lambda d=data: PIPELINE.analyze_iso(d, REG), 20)
        print(f"camt.054 {n} entries: {_stats(lat)}")

    doc = secure_parse((FIXTURES / "camt053-00114-valid.xml").read_bytes())
    lat = _timed(lambda: validate_message(doc.root, "camt.053.001.14"), 100)
    print(f"camt.053 schema validation: {_stats(lat)}")

    entry = AccountEntry(
        end_to_end_id="E2E-0001",
        transaction_id="TX-0001",
        amount=MonetaryAmount(amount_minor=1250000, currency="EUR"),
        currency="EUR",
        credit_debit=CreditDebitIndicator.DBIT,
    )
    account = AccountReference(iban="IT60X0542811101000000123456", currency="EUR")
    context = LifecycleAccountContext(
        end_to_end_id="E2E-0001",
        transaction_id="TX-0001",
        amount_minor=1250000,
        currency="EUR",
        debtor_account="IT60X0542811101000000123456",
    )
    lat = _timed(lambda: reconcile_account_entry(entry, account, context), 2000)
    print(f"single account reconciliation: {_stats(lat)}")


if __name__ == "__main__":
    main()
