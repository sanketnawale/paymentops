"""Operator dashboard summary API (tenant-scoped, real DB data)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from paymentops_api.auth import AuthenticatedClient, get_api_client, get_db
from paymentops_api.db.models import AccountEntryRow, BatchJob, PaymentCase

router = APIRouter(tags=["dashboard"])


@router.get("/api/v1/dashboard")
async def dashboard(
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    org = client.organization_id

    readiness = await _count_by(
        session, PaymentCase.address_readiness, PaymentCase.organization_id, org
    )
    open_cases = await session.scalar(
        select(func.count())
        .select_from(PaymentCase)
        .where(
            PaymentCase.organization_id == org,
            PaymentCase.status.in_(["NEW", "ANALYZED", "REPAIR_PROPOSED", "REVIEW_REQUIRED"]),
        )
    )
    running_batches = await session.scalar(
        select(func.count())
        .select_from(BatchJob)
        .where(BatchJob.organization_id == org, BatchJob.status == "RUNNING")
    )

    # Top rule findings from the most recent cases (via rule_findings).
    top_findings: dict[str, int] = {}
    from paymentops_api.db.models import RuleFinding

    result = await session.execute(
        select(RuleFinding.rule_id, func.count())
        .where(RuleFinding.organization_id == org)
        .group_by(RuleFinding.rule_id)
    )
    for rule_id, count in result.all():
        top_findings[str(rule_id)] = int(count)

    # Week 6 account-reconciliation metrics.
    account = await _count_by(
        session, AccountEntryRow.reconciliation_status, AccountEntryRow.organization_id, org
    )
    total_entries = sum(account.values())
    reconciled = account.get("RECONCILED", 0)

    return {
        "analyzed": int(sum(readiness.values())),
        "ready": readiness.get("READY", 0),
        "repairable": readiness.get("REPAIRABLE", 0),
        "review_required": readiness.get("REVIEW_REQUIRED", 0),
        "unresolved": readiness.get("UNRESOLVED", 0),
        "open_cases": int(open_cases or 0),
        "running_batches": int(running_batches or 0),
        "top_findings": dict(sorted(top_findings.items(), key=lambda x: -x[1])[:10]),
        "account_entries": total_entries,
        "account_reconciled": reconciled,
        "missing_account_event": account.get("MISSING_ACCOUNT_EVENT", 0),
        "account_mismatches": account.get("ACCOUNT_MISMATCH", 0)
        + account.get("AMOUNT_MISMATCH", 0)
        + account.get("CURRENCY_MISMATCH", 0),
        "unmatched_entries": account.get("UNMATCHED_ACCOUNT_ENTRY", 0),
        "duplicate_entries": account.get("DUPLICATE_ACCOUNT_ENTRY", 0),
        "reconciliation_rate": round(100.0 * reconciled / total_entries, 2)
        if total_entries
        else 0.0,
    }


async def _count_by(
    session: AsyncSession, column: Any, org_column: Any, org: str
) -> dict[str, int]:
    result = await session.execute(
        select(column, func.count()).where(org_column == org).group_by(column)
    )
    return {str(k): int(v) for k, v in result.all()}
