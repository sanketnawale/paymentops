"""camt.053.001.14 / camt.054.001.14 adapter tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from iso_engine import (
    build_default_registry,
    map_camt053_to_account_report,
    map_camt054_to_account_report,
    secure_parse,
    validate_message,
)
from iso_engine.camt053.namespace import SUPPORTED_CAMT_053_VERSIONS
from iso_engine.camt054.namespace import SUPPORTED_CAMT_054_VERSIONS
from payment_domain.models import (
    AccountReportBundle,
    AccountReportType,
    BalanceType,
    CreditDebitIndicator,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "iso"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_camt054_adapter_maps_notification():
    doc = secure_parse(_load("camt054-00114-valid-debit.xml"))
    bundle = map_camt054_to_account_report(doc.root, SUPPORTED_CAMT_054_VERSIONS["camt.054.001.14"])
    assert isinstance(bundle, AccountReportBundle)
    assert bundle.report_type == AccountReportType.NOTIFICATION
    assert len(bundle.reports) == 1
    report = bundle.reports[0]
    assert report.notification_id == "NTFCTN-0001"
    assert report.account.iban == "IT60X0542811101000000123456"
    assert report.account.currency == "EUR"
    entry = report.entries[0]
    assert entry.end_to_end_id == "E2E-0001"
    assert entry.instruction_id == "INSTR-0001"
    assert entry.transaction_id == "TX-0001"
    assert entry.amount.amount_minor == 1250000
    assert entry.currency == "EUR"
    assert entry.credit_debit == CreditDebitIndicator.DBIT
    assert entry.booking_date.isoformat() == "2026-01-12"
    assert entry.bank_transaction_code.code == "PMNT"
    assert entry.bank_transaction_code.family == "ICDT"
    assert entry.account_servicer_reference == "ASR-0001"
    assert entry.remittance_reference == "Invoice INV-92881"


def test_camt054_validation_passes():
    doc = secure_parse(_load("camt054-00114-valid-debit.xml"))
    assert validate_message(doc.root, "camt.054.001.14").valid


def test_camt053_adapter_maps_statement():
    doc = secure_parse(_load("camt053-00114-valid.xml"))
    bundle = map_camt053_to_account_report(doc.root, SUPPORTED_CAMT_053_VERSIONS["camt.053.001.14"])
    assert bundle.report_type == AccountReportType.STATEMENT
    report = bundle.reports[0]
    assert report.statement_id == "STMT-0001"
    assert report.account.iban == "IT60X0542811101000000123456"
    assert report.period_start.isoformat() == "2026-01-12"
    assert report.period_end.isoformat() == "2026-01-12"
    assert len(report.balances) == 2
    types = {b.type for b in report.balances}
    assert BalanceType.OPENING in types and BalanceType.CLOSING in types
    assert report.entries[0].end_to_end_id == "E2E-0001"


def test_camt053_validation_passes():
    doc = secure_parse(_load("camt053-00114-valid.xml"))
    assert validate_message(doc.root, "camt.053.001.14").valid


def test_camt_registry_resolution():
    reg = build_default_registry()
    assert "camt.053.001.14" in reg
    assert "camt.054.001.14" in reg
    with pytest.raises(Exception):
        reg.resolve("camt.053.001.08")


def test_camt_entry_identity_hash_deterministic():
    doc = secure_parse(_load("camt054-00114-valid-debit.xml"))
    bundle = map_camt054_to_account_report(doc.root, SUPPORTED_CAMT_054_VERSIONS["camt.054.001.14"])
    entry = bundle.reports[0].entries[0]
    assert entry.identity_hash == entry.identity_hash
    assert len(entry.identity_hash) == 64
