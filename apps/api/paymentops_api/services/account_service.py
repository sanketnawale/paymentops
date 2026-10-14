"""Account-reporting service: persist camt reports/entries, correlate to payment lifecycles,
run deterministic account reconciliation, detect missing events, and manage exceptions.

Analytical only. Never touches a bank ledger. Tenant-scoped by ``organization_id``.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

from paymentops_api.db.models import (
    AccountBalanceRow,
    AccountEntryRow,
    AccountReconciliationRow,
    AccountReportRow,
    AuditEvent,
    PaymentCase,
    PaymentLifecycleRow,
)
from paymentops_api.observability import (
    account_entries_total,
    account_reconciliations_total,
    account_reports_total,
    missing_account_events_total,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from iso_engine.account.identity import LifecycleAccountContext
from iso_engine.account.reconciliation import reconcile_account_entry
from payment_domain.models import (
    AccountEntry,
    AccountReconciliationStatus,
    AccountReport,
)

# Development default: an account event is expected within this many hours of acceptance.
DEFAULT_ACCOUNT_WINDOW_HOURS = 48

_EXCEPTION_STATUSES = {
    AccountReconciliationStatus.MISSING_ACCOUNT_EVENT.value,
    AccountReconciliationStatus.AMOUNT_MISMATCH.value,
    AccountReconciliationStatus.CURRENCY_MISMATCH.value,
    AccountReconciliationStatus.ACCOUNT_MISMATCH.value,
    AccountReconciliationStatus.DUPLICATE_ACCOUNT_ENTRY.value,
    AccountReconciliationStatus.REVIEW_REQUIRED.value,
}


async def ingest_account_report(
    session: AsyncSession,
    org: str,
    result: Any,
    iso_message_id: Any,
) -> list[AccountReportRow]:
    """Persist a camt report bundle, then correlate + reconcile each entry."""
    reports = [AccountReport.model_validate(r) for r in (result.account_reports or [])]
    persisted: list[AccountReportRow] = []
    for report in reports:
        row = await _persist_report(session, org, report, iso_message_id)
        persisted.append(row)
        account_reports_total.labels(
            report_type=report.report_type.value,
            version=report.message_version or "unknown",
        ).inc()
        await _persist_balances(session, org, report, row)
        for entry in report.entries:
            await _ingest_entry(session, org, entry, report, row)
    return persisted


async def _persist_report(
    session: AsyncSession, org: str, report: AccountReport, iso_message_id: Any
) -> AccountReportRow:
    acct = report.account
    row = AccountReportRow(
        organization_id=org,
        iso_message_id=iso_message_id,
        message_id=report.message_id,
        message_definition=report.message_definition or "unknown",
        message_version=report.message_version or "unknown",
        report_type=report.report_type.value,
        account_iban=acct.iban if acct else None,
        account_other_id=acct.other_identification if acct else None,
        account_currency=acct.currency if acct else None,
        servicer_bic=acct.servicer_bic if acct else None,
        statement_id=report.statement_id,
        notification_id=report.notification_id,
        period_start=report.period_start,
        period_end=report.period_end,
        entry_count=report.number_of_entries,
        source_hash=report.source_hash,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def _persist_balances(
    session: AsyncSession, org: str, report: AccountReport, row: AccountReportRow
) -> None:
    for bal in report.balances:
        session.add(
            AccountBalanceRow(
                organization_id=org,
                report_id=row.id,
                balance_type=bal.type.value,
                amount_minor=bal.amount.amount_minor,
                currency=bal.amount.currency,
                credit_debit=bal.credit_debit.value,
                created_at=datetime.now(UTC),
            )
        )
    if report.balances:
        await session.commit()


async def _ingest_entry(
    session: AsyncSession,
    org: str,
    entry: AccountEntry,
    report: AccountReport,
    report_row: AccountReportRow,
) -> None:
    identity_hash = entry.identity_hash
    # Duplicate / cross-report confirmation detection (same org + identity hash).
    existing = await _find_entry_by_identity(session, org, identity_hash)
    duplicate_status: AccountReconciliationStatus | None = None
    if existing is not None:
        existing_report_type = await _report_type_of(session, existing.report_id)
        if existing.report_id == report_row.id or existing_report_type == report.report_type.value:
            duplicate_status = AccountReconciliationStatus.DUPLICATE_ACCOUNT_ENTRY
        else:
            # camt.054 then camt.053 (or vice versa) -> same event confirmed.
            duplicate_status = AccountReconciliationStatus.RECONCILED

    entry_row = _entry_to_row(org, entry, report_row, identity_hash)
    session.add(entry_row)
    await session.commit()
    await session.refresh(entry_row)
    account_entries_total.labels(credit_debit=entry_row.credit_debit or "UNKNOWN").inc()

    if duplicate_status is not None:
        entry_row.reconciliation_status = duplicate_status.value
        entry_row.evidence = (
            ["ACCOUNT_EVENT_CONFIRMED"]
            if duplicate_status == AccountReconciliationStatus.RECONCILED
            else ["DUPLICATE_IDENTITY"]
        )
        entry_row.lifecycle_id = existing.lifecycle_id if existing is not None else None
        await session.commit()
        if duplicate_status == AccountReconciliationStatus.RECONCILED and entry_row.lifecycle_id:
            await _add_lifecycle_event(
                session, org, entry_row.lifecycle_id, entry, report, "ACCOUNT_EVENT_CONFIRMED"
            )
        elif duplicate_status == AccountReconciliationStatus.DUPLICATE_ACCOUNT_ENTRY:
            await _ensure_case(session, org, entry_row, "DUPLICATE_ACCOUNT_ENTRY")
        return

    lifecycle = await _find_lifecycle_for_entry(session, org, entry)
    await _reconcile_and_persist(session, org, entry_row, entry, report, lifecycle)


def _entry_to_row(
    org: str, entry: AccountEntry, report_row: AccountReportRow, identity_hash: str
) -> AccountEntryRow:
    amount = entry.amount
    btc = entry.bank_transaction_code
    return AccountEntryRow(
        organization_id=org,
        report_id=report_row.id,
        entry_reference=entry.entry_reference,
        account_servicer_reference=entry.account_servicer_reference,
        transaction_id=entry.transaction_id,
        instruction_id=entry.instruction_id,
        end_to_end_id=entry.end_to_end_id,
        uetr=entry.uetr,
        amount_minor=amount.amount_minor if amount else None,
        currency=entry.currency or (amount.currency if amount else None),
        credit_debit=entry.credit_debit.value if entry.credit_debit else None,
        booking_date=entry.booking_date,
        value_date=entry.value_date,
        status=entry.status,
        bank_tx_code=btc.code if btc else None,
        bank_tx_family=btc.family if btc else None,
        bank_tx_sub_family=btc.sub_family if btc else None,
        remittance_reference=entry.remittance_reference,
        identity_hash=identity_hash,
        source_hash=entry.source_hash,
        created_at=datetime.now(UTC),
    )


async def _reconcile_and_persist(
    session: AsyncSession,
    org: str,
    entry_row: AccountEntryRow,
    entry: AccountEntry,
    report: AccountReport,
    lifecycle: PaymentLifecycleRow | None,
) -> None:
    if lifecycle is None:
        entry_row.reconciliation_status = AccountReconciliationStatus.UNMATCHED_ACCOUNT_ENTRY.value
        entry_row.evidence = []
        entry_row.conflicts = []
        await session.commit()
        await _persist_reconciliation(
            session,
            org,
            entry_row,
            None,
            AccountReconciliationStatus.UNMATCHED_ACCOUNT_ENTRY,
            0.0,
            [],
            [],
        )
        return

    context = LifecycleAccountContext(
        message_id=lifecycle.original_message_id,
        original_message_id=lifecycle.original_message_id,
        transaction_id=lifecycle.transaction_id,
        end_to_end_id=lifecycle.end_to_end_id,
        instruction_id=lifecycle.instruction_id,
        uetr=lifecycle.uetr,
        reference=None,
        amount_minor=lifecycle.amount_minor,
        currency=lifecycle.currency,
        debtor_account=lifecycle.debtor_account,
        creditor_account=lifecycle.creditor_account,
    )
    result = reconcile_account_entry(entry, report.account, context)

    entry_row.reconciliation_status = result.classification.value
    entry_row.match_score = result.match_score
    entry_row.evidence = result.evidence
    entry_row.conflicts = result.conflicts
    entry_row.lifecycle_id = lifecycle.id
    await session.commit()

    await _persist_reconciliation(
        session,
        org,
        entry_row,
        lifecycle.id,
        result.classification,
        result.match_score,
        result.evidence,
        result.conflicts,
    )
    account_reconciliations_total.labels(classification=result.classification.value).inc()
    event_type = (
        "DEBIT_RECORDED"
        if (entry.credit_debit and entry.credit_debit.value == "DBIT")
        else "CREDIT_RECORDED"
    )
    await _add_lifecycle_event(session, org, lifecycle.id, entry, report, event_type)

    if result.classification.value in _EXCEPTION_STATUSES:
        await _ensure_case(session, org, entry_row, result.classification.value)


async def _find_entry_by_identity(
    session: AsyncSession, org: str, identity_hash: str
) -> AccountEntryRow | None:
    result = await session.execute(
        select(AccountEntryRow).where(
            AccountEntryRow.organization_id == org, AccountEntryRow.identity_hash == identity_hash
        )
    )
    return result.scalars().first()


async def _report_type_of(session: AsyncSession, report_id: Any) -> str | None:
    result = await session.execute(
        select(AccountReportRow.report_type).where(AccountReportRow.id == report_id)
    )
    return result.scalar_one_or_none()


async def _find_lifecycle_for_entry(
    session: AsyncSession, org: str, entry: AccountEntry
) -> PaymentLifecycleRow | None:
    conds = []
    if entry.uetr:
        conds.append(PaymentLifecycleRow.uetr == entry.uetr)
    if entry.transaction_id:
        conds.append(PaymentLifecycleRow.transaction_id == entry.transaction_id)
    if entry.end_to_end_id:
        conds.append(PaymentLifecycleRow.end_to_end_id == entry.end_to_end_id)
    if entry.instruction_id:
        conds.append(PaymentLifecycleRow.instruction_id == entry.instruction_id)
    if not conds:
        return None
    from sqlalchemy import or_

    result = await session.execute(
        select(PaymentLifecycleRow).where(PaymentLifecycleRow.organization_id == org, or_(*conds))
    )
    return result.scalars().first()


async def _persist_reconciliation(
    session: AsyncSession,
    org: str,
    entry_row: AccountEntryRow,
    lifecycle_id: Any,
    classification: AccountReconciliationStatus,
    match_score: float,
    evidence: list[str],
    conflicts: list[str],
) -> AccountReconciliationRow:
    row = AccountReconciliationRow(
        organization_id=org,
        account_entry_id=entry_row.id,
        lifecycle_id=lifecycle_id,
        classification=classification.value,
        match_score=match_score,
        evidence=evidence,
        conflicts=conflicts,
        status="PENDING",
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def _add_lifecycle_event(
    session: AsyncSession,
    org: str,
    lifecycle_id: Any,
    entry: AccountEntry,
    report: AccountReport,
    event_type: str,
) -> None:
    from paymentops_api.db.models import PaymentLifecycleEventRow

    session.add(
        PaymentLifecycleEventRow(
            organization_id=org,
            lifecycle_id=lifecycle_id,
            event_type=event_type,
            message_family="camt",
            message_definition=report.message_definition,
            message_version=report.message_version,
            message_id=entry.source_message_id,
            timestamp=datetime.now(UTC),
            status=entry.status or "BOOK",
            raw_status_code=entry.status,
            reasons=[],
            correlation_evidence=entry.evidence,
            source_hash=entry.source_hash,
        )
    )
    await session.commit()


async def _ensure_case(
    session: AsyncSession, org: str, entry_row: AccountEntryRow, classification: str
) -> None:
    """Create a single PaymentCase per (entry, classification) exception (idempotent)."""
    case_id = f"case-acct-{entry_row.identity_hash[:16]}"
    existing = await session.execute(
        select(PaymentCase).where(
            PaymentCase.case_id == case_id, PaymentCase.organization_id == org
        )
    )
    if existing.scalars().first() is not None:
        return
    session.add(
        PaymentCase(
            case_id=case_id,
            organization_id=org,
            message_type=classification,
            status="REVIEW_REQUIRED",
            created_at=datetime.now(UTC),
        )
    )
    session.add(
        AuditEvent(
            organization_id=org,
            case_id=case_id,
            event_type="account_exception.created",
            action_metadata={"classification": classification, "entry_id": str(entry_row.id)},
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()


# ---------------------------------------------------------------- missing account events


async def detect_missing_account_events(
    session: AsyncSession,
    org: str,
    *,
    window_hours: int = DEFAULT_ACCOUNT_WINDOW_HOURS,
) -> list[str]:
    """Lifecycles that reached ACCEPTED but have no account event within the window."""
    cutoff = datetime.now(UTC) - timedelta(hours=window_hours)
    result = await session.execute(
        select(PaymentLifecycleRow).where(
            PaymentLifecycleRow.organization_id == org,
            PaymentLifecycleRow.current_status == "ACCEPTED",
            PaymentLifecycleRow.created_at < cutoff,
        )
    )
    flagged: list[str] = []
    for lifecycle in result.scalars().all():
        has_event = await session.execute(
            select(AccountEntryRow).where(
                AccountEntryRow.organization_id == org,
                AccountEntryRow.lifecycle_id == lifecycle.id,
            )
        )
        if has_event.scalars().first() is not None:
            continue
        case_id = f"case-missing-{lifecycle.lifecycle_id}"
        existing = await session.execute(
            select(PaymentCase).where(
                PaymentCase.case_id == case_id, PaymentCase.organization_id == org
            )
        )
        if existing.scalars().first() is None:
            session.add(
                PaymentCase(
                    case_id=case_id,
                    organization_id=org,
                    message_type="MISSING_ACCOUNT_EVENT",
                    status="REVIEW_REQUIRED",
                    created_at=datetime.now(UTC),
                )
            )
            await session.commit()
        flagged.append(lifecycle.lifecycle_id)
        missing_account_events_total.inc()
    return flagged


# ---------------------------------------------------------------- reads / decisions


async def list_account_reports(
    session: AsyncSession,
    org: str,
    *,
    report_type: str | None = None,
    account: str | None = None,
    limit: int = 100,
) -> list[AccountReportRow]:
    stmt = select(AccountReportRow).where(AccountReportRow.organization_id == org)
    if report_type:
        stmt = stmt.where(AccountReportRow.report_type == report_type)
    if account:
        stmt = stmt.where(AccountReportRow.account_iban == account)
    stmt = stmt.order_by(AccountReportRow.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_account_report(session: AsyncSession, org: str, report_id: str) -> AccountReportRow:
    result = await session.execute(
        select(AccountReportRow).where(
            AccountReportRow.id == report_id, AccountReportRow.organization_id == org
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise LookupError("account report not found")
    return row


async def list_account_entries(
    session: AsyncSession,
    org: str,
    *,
    report_id: str | None = None,
    credit_debit: str | None = None,
    reconciliation_status: str | None = None,
    limit: int = 200,
) -> list[AccountEntryRow]:
    stmt = select(AccountEntryRow).where(AccountEntryRow.organization_id == org)
    if report_id:
        stmt = stmt.where(AccountEntryRow.report_id == report_id)
    if credit_debit:
        stmt = stmt.where(AccountEntryRow.credit_debit == credit_debit)
    if reconciliation_status:
        stmt = stmt.where(AccountEntryRow.reconciliation_status == reconciliation_status)
    stmt = stmt.order_by(AccountEntryRow.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_account_entry(session: AsyncSession, org: str, entry_id: str) -> AccountEntryRow:
    result = await session.execute(
        select(AccountEntryRow).where(
            AccountEntryRow.id == entry_id, AccountEntryRow.organization_id == org
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise LookupError("account entry not found")
    return row


async def list_account_reconciliations(
    session: AsyncSession, org: str, *, limit: int = 200
) -> list[AccountReconciliationRow]:
    result = await session.execute(
        select(AccountReconciliationRow)
        .where(AccountReconciliationRow.organization_id == org)
        .order_by(AccountReconciliationRow.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_account_reconciliation(
    session: AsyncSession, org: str, reconciliation_id: str
) -> AccountReconciliationRow:
    result = await session.execute(
        select(AccountReconciliationRow).where(
            AccountReconciliationRow.id == reconciliation_id,
            AccountReconciliationRow.organization_id == org,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise LookupError("account reconciliation not found")
    return row


async def decide_account_reconciliation(
    session: AsyncSession,
    org: str,
    reconciliation_id: str,
    action: str,
    *,
    operator: str | None,
    note: str | None,
) -> AccountReconciliationRow:
    row = await get_account_reconciliation(session, org, reconciliation_id)
    if action not in ("confirm", "reject", "duplicate", "review"):
        raise ValueError(f"unsupported action '{action}'")
    status_map = {
        "confirm": "CONFIRMED",
        "reject": "REJECTED",
        "duplicate": "DUPLICATE",
        "review": "REVIEW_REQUIRED",
    }
    row.status = status_map[action]
    row.operator = operator
    row.note = note
    row.decided_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(row)
    return row


def entry_identity_hash(entry: AccountEntry) -> str:
    return hashlib.sha256(entry.model_dump_json().encode("utf-8")).hexdigest()
