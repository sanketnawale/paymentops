"""Account-reporting API (camt.053 / camt.054 analysis + reconciliation).

Non-transactional: reconciliation decisions are analytical only and never modify a bank
ledger. All endpoints are tenant-scoped.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from paymentops_api.auth import (
    AuthenticatedClient,
    get_actor_identity,
    get_api_client,
    get_db,
)
from paymentops_api.db.models import (
    AccountBalanceRow,
    AccountEntryRow,
    AccountReconciliationRow,
    AccountReportRow,
)
from paymentops_api.services import account_service

router = APIRouter(tags=["account-reporting"])


class DecideReconciliationRequest(BaseModel):
    action: str
    operator: str | None = None
    note: str | None = None


class MissingEventRequest(BaseModel):
    window_hours: int = 48


@router.get("/api/v1/account-reports")
async def list_account_reports(
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
    report_type: str | None = None,
    account: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    rows = await account_service.list_account_reports(
        session, client.organization_id, report_type=report_type, account=account, limit=limit
    )
    return [_report_dict(r) for r in rows]


@router.get("/api/v1/account-reports/{report_id}")
async def get_account_report(
    report_id: str,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        report = await account_service.get_account_report(
            session, client.organization_id, report_id
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="account report not found") from None
    entries = await account_service.list_account_entries(
        session, client.organization_id, report_id=report_id
    )
    balances = await _balances(session, client.organization_id, report_id)
    data = _report_dict(report)
    data["balances"] = [_balance_dict(b) for b in balances]
    data["entries"] = [_entry_dict(e) for e in entries]
    data["reconciliation_summary"] = _reconciliation_summary(entries)
    return data


@router.get("/api/v1/account-entries")
async def list_account_entries(
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
    report_id: str | None = None,
    credit_debit: str | None = None,
    reconciliation_status: str | None = None,
    limit: int = 200,
) -> list[dict[str, object]]:
    rows = await account_service.list_account_entries(
        session,
        client.organization_id,
        report_id=report_id,
        credit_debit=credit_debit,
        reconciliation_status=reconciliation_status,
        limit=limit,
    )
    return [_entry_dict(e) for e in rows]


@router.get("/api/v1/account-entries/{entry_id}")
async def get_account_entry(
    entry_id: str,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        entry = await account_service.get_account_entry(session, client.organization_id, entry_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="account entry not found") from None
    return _entry_dict(entry)


@router.post("/api/v1/account-reconciliation/run")
async def run_account_reconciliation(
    body: MissingEventRequest,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    flagged = await account_service.detect_missing_account_events(
        session, client.organization_id, window_hours=body.window_hours
    )
    return {"missing_account_events": flagged, "count": len(flagged)}


@router.get("/api/v1/account-reconciliations")
async def list_account_reconciliations(
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
    limit: int = 200,
) -> list[dict[str, object]]:
    rows = await account_service.list_account_reconciliations(
        session, client.organization_id, limit=limit
    )
    return [_reconciliation_dict(r) for r in rows]


@router.get("/api/v1/account-reconciliations/{reconciliation_id}")
async def get_account_reconciliation(
    reconciliation_id: str,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        row = await account_service.get_account_reconciliation(
            session, client.organization_id, reconciliation_id
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="account reconciliation not found") from None
    return _reconciliation_dict(row)


@router.post("/api/v1/account-reconciliations/{reconciliation_id}/decide")
async def decide_account_reconciliation(
    reconciliation_id: str,
    body: DecideReconciliationRequest,
    client: AuthenticatedClient = Depends(get_api_client),
    actor: str | None = Depends(get_actor_identity),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        row = await account_service.decide_account_reconciliation(
            session,
            client.organization_id,
            reconciliation_id,
            body.action,
            operator=actor or body.operator,
            note=body.note,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="account reconciliation not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return {"reconciliation_id": str(row.id), "status": row.status, "action": body.action}


@router.get("/api/v1/account-reconciliation/report")
async def account_reconciliation_report(
    request: Request,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> Response:
    rows = await account_service.list_account_reconciliations(session, client.organization_id)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "lifecycle_reference",
            "account_entry_reference",
            "amount",
            "currency",
            "credit_debit",
            "classification",
            "match_score",
            "critical_conflict",
            "review_required",
        ]
    )
    for row in rows:
        entry = await _entry_by_id(session, client.organization_id, row.account_entry_id)
        writer.writerow(
            [
                _safe_csv(str(row.lifecycle_id) if row.lifecycle_id else ""),
                _safe_csv(entry.entry_reference if entry else ""),
                entry.amount_minor if entry else "",
                _safe_csv(entry.currency if entry else ""),
                _safe_csv(entry.credit_debit if entry else ""),
                _safe_csv(row.classification),
                row.match_score,
                _safe_csv(",".join(row.conflicts)),
                _safe_csv(row.status),
            ]
        )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="account-reconciliation.csv"'},
    )


# ---------------------------------------------------------------- helpers


async def _balances(session: AsyncSession, org: str, report_id: str) -> list[AccountBalanceRow]:
    from sqlalchemy import select

    result = await session.execute(
        select(AccountBalanceRow).where(
            AccountBalanceRow.organization_id == org, AccountBalanceRow.report_id == report_id
        )
    )
    return list(result.scalars().all())


async def _entry_by_id(session: AsyncSession, org: str, entry_id: Any) -> AccountEntryRow | None:
    from sqlalchemy import select

    result = await session.execute(
        select(AccountEntryRow).where(
            AccountEntryRow.id == entry_id, AccountEntryRow.organization_id == org
        )
    )
    return result.scalar_one_or_none()


def _reconciliation_summary(entries: list[AccountEntryRow]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for e in entries:
        key = e.reconciliation_status or "PENDING"
        summary[key] = summary.get(key, 0) + 1
    return summary


def _report_dict(r: AccountReportRow) -> dict[str, object]:
    return {
        "id": str(r.id),
        "message_id": r.message_id,
        "message_definition": r.message_definition,
        "message_version": r.message_version,
        "report_type": r.report_type,
        "account_iban": r.account_iban,
        "account_currency": r.account_currency,
        "statement_id": r.statement_id,
        "notification_id": r.notification_id,
        "period_start": r.period_start.isoformat() if r.period_start else None,
        "period_end": r.period_end.isoformat() if r.period_end else None,
        "entry_count": r.entry_count,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _balance_dict(b: AccountBalanceRow) -> dict[str, object]:
    return {
        "balance_type": b.balance_type,
        "amount_minor": b.amount_minor,
        "currency": b.currency,
        "credit_debit": b.credit_debit,
    }


def _entry_dict(e: AccountEntryRow) -> dict[str, object]:
    return {
        "id": str(e.id),
        "report_id": str(e.report_id),
        "entry_reference": e.entry_reference,
        "account_servicer_reference": e.account_servicer_reference,
        "transaction_id": e.transaction_id,
        "instruction_id": e.instruction_id,
        "end_to_end_id": e.end_to_end_id,
        "uetr": e.uetr,
        "amount_minor": e.amount_minor,
        "currency": e.currency,
        "credit_debit": e.credit_debit,
        "booking_date": e.booking_date.isoformat() if e.booking_date else None,
        "value_date": e.value_date.isoformat() if e.value_date else None,
        "status": e.status,
        "bank_tx_code": e.bank_tx_code,
        "bank_tx_family": e.bank_tx_family,
        "bank_tx_sub_family": e.bank_tx_sub_family,
        "remittance_reference": e.remittance_reference,
        "reconciliation_status": e.reconciliation_status,
        "match_score": e.match_score,
        "lifecycle_id": str(e.lifecycle_id) if e.lifecycle_id else None,
        "evidence": e.evidence,
        "conflicts": e.conflicts,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


def _reconciliation_dict(r: AccountReconciliationRow) -> dict[str, object]:
    return {
        "id": str(r.id),
        "account_entry_id": str(r.account_entry_id),
        "lifecycle_id": str(r.lifecycle_id) if r.lifecycle_id else None,
        "classification": r.classification,
        "match_score": r.match_score,
        "evidence": r.evidence,
        "conflicts": r.conflicts,
        "status": r.status,
        "operator": r.operator,
        "note": r.note,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _safe_csv(value: Any) -> str:
    s = str(value) if value is not None else ""
    if s.startswith(("=", "+", "-", "@")):
        return "'" + s
    return s
