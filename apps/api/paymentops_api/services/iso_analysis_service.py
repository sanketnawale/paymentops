"""ISO analysis service: registry-based ISO ingestion + lifecycle correlation.

Analytical state only. Never transactional. Tenant-scoped by ``organization_id``.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from paymentops_api.db.models import (
    IsoMessage,
    PaymentLifecycleEventRow,
    PaymentLifecycleRow,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from analysis.models import IsoAnalysisResult
from analysis.pipeline import AnalysisPipeline
from iso_engine.lifecycle.correlation import CorrelationProfile, correlate_profiles
from iso_engine.registry import IsoMessageRegistry

ENGINE_VERSION = "0.3.0"


async def analyze_iso_message(
    session: AsyncSession,
    org: str,
    payload: bytes,
    *,
    registry: IsoMessageRegistry,
    pipeline: AnalysisPipeline,
    max_transactions: int = 100,
) -> IsoAnalysisResult:
    """Run the registry-based ISO pipeline and persist message + lifecycle state."""
    result = pipeline.analyze_iso(payload, registry, max_transactions=max_transactions)

    # Idempotency: same org + message_hash -> return existing analysis (no duplicate event).
    msg_hash = _message_hash_from_result(result)
    existing = await _find_by_hash(session, org, msg_hash)
    if existing is not None:
        result.lifecycle_id = await _lifecycle_id_for_message(session, org, str(existing.id))
        return result

    iso_row = await _persist_iso_message(session, org, result, msg_hash)
    if result.account_reports:
        from paymentops_api.services import account_service

        reports = await account_service.ingest_account_report(session, org, result, iso_row.id)
        result.account_report_ids = [str(r.id) for r in reports]
        result.correlation_status = _account_correlation_status(result.account_reports)
    else:
        await _correlate_and_build_lifecycle(session, org, result, iso_row)
    return result


def _account_correlation_status(reports: list[dict[str, Any]]) -> str:
    classifications = {
        entry.get("reconciliation_status")
        for report in reports
        for entry in (report.get("entries") or [])
        if entry.get("reconciliation_status")
    }
    if "RECONCILED" in classifications:
        return "CORRELATED"
    if classifications:
        return "UNRESOLVED"
    return "UNRESOLVED"


def _message_hash_from_result(result: IsoAnalysisResult) -> str:
    payload = {
        "family": result.message_family,
        "version": result.message_version,
        "message_id": result.message_id,
        "hash": result.input_hash,
    }
    return hashlib.sha256(str(payload).encode("utf-8")).hexdigest()


async def _find_by_hash(session: AsyncSession, org: str, msg_hash: str) -> IsoMessage | None:
    result = await session.execute(
        select(IsoMessage).where(
            IsoMessage.organization_id == org, IsoMessage.message_hash == msg_hash
        )
    )
    return result.scalars().first()


async def _lifecycle_id_for_message(session: AsyncSession, org: str, iso_id: Any) -> str | None:
    result = await session.execute(
        select(PaymentLifecycleEventRow).where(
            PaymentLifecycleEventRow.organization_id == org,
            PaymentLifecycleEventRow.message_id == iso_id,
        )
    )
    event = result.scalars().first()
    return str(event.lifecycle_id) if event else None


async def _persist_iso_message(
    session: AsyncSession, org: str, result: IsoAnalysisResult, msg_hash: str
) -> IsoMessage:
    row = IsoMessage(
        organization_id=org,
        message_id=result.message_id,
        message_family=result.message_family or "unknown",
        message_definition=result.message_definition or "unknown",
        message_version=result.message_version or "unknown",
        namespace=result.namespace or "",
        source_adapter=f"{result.message_family}_{result.message_version}",
        adapter_version=result.adapter_version or "0.0.0",
        schema_version=result.schema_version or "",
        schema_validation=result.schema_validation,
        message_hash=msg_hash,
        input_hash=result.input_hash,
        canonical_model_version=result.canonical_model_version,
        engine_version=result.engine_version or ENGINE_VERSION,
        status="ANALYZED",
        raw_status=result.raw_status,
        normalized_status=result.normalized_status,
        processed_at=result.processed_at,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def _correlate_and_build_lifecycle(
    session: AsyncSession, org: str, result: IsoAnalysisResult, iso_row: IsoMessage
) -> None:
    """Correlate the message to an existing lifecycle (or create one) and add an event."""
    event_type = _event_type_for(result.message_version, result.normalized_status)

    # Status report (pacs.002): reference existing lifecycle; do NOT create a fake one.
    if result.message_version and result.message_version.startswith("pacs.002"):
        for profile_dict in result.correlation_profiles:
            profile = _profile_from_dict(profile_dict)
            lifecycle = await _find_lifecycle(session, org, profile)
            if lifecycle is None:
                # Out-of-order / unknown parent -> UNRESOLVED, no fake correlation.
                result.correlation_status = "UNRESOLVED"
                continue
            correlation = correlate_profiles(profile, _profile_from_lifecycle(lifecycle))
            result.correlation_status = correlation.status.value
            result.correlation_evidence = correlation.evidence
            result.correlation_conflicts = correlation.conflicts
            result.lifecycle_id = str(lifecycle.id)
            await _add_event(session, org, lifecycle, result, iso_row, event_type, correlation)
            if result.normalized_status:
                lifecycle.current_status = result.normalized_status
                lifecycle.updated_at = datetime.now(UTC)
                await session.commit()
        return

    # Payment/initiation messages (pain.001 / pacs.008 / pacs.009): create or update lifecycle.
    for profile_dict in result.correlation_profiles:
        profile = _profile_from_dict(profile_dict)
        lifecycle = await _find_lifecycle(session, org, profile)
        if lifecycle is None:
            lifecycle = PaymentLifecycleRow(
                organization_id=org,
                lifecycle_id=f"life-{uuid4().hex[:12]}",
                end_to_end_id=profile.end_to_end_id,
                instruction_id=profile.instruction_id,
                transaction_id=profile.transaction_id,
                original_message_id=profile.original_message_id,
                debtor_account=profile.debtor_account,
                creditor_account=profile.creditor_account,
                amount_minor=profile.amount,
                currency=profile.currency,
                current_status="UNKNOWN",
                created_at=datetime.now(UTC),
            )
            session.add(lifecycle)
            await session.commit()
            await session.refresh(lifecycle)
            result.correlation_status = "CORRELATED" if profile.end_to_end_id else "UNRESOLVED"
            result.correlation_evidence = []
            result.lifecycle_id = str(lifecycle.id)
        else:
            correlation = correlate_profiles(profile, _profile_from_lifecycle(lifecycle))
            result.correlation_status = correlation.status.value
            result.correlation_evidence = correlation.evidence
            result.correlation_conflicts = correlation.conflicts
            result.lifecycle_id = str(lifecycle.id)
        await _add_event(session, org, lifecycle, result, iso_row, event_type, None)

    if result.lifecycle_id:
        await _update_lifecycle_status(session, result)


def _event_type_for(message_version: str | None, normalized_status: str | None) -> str:
    if message_version and message_version.startswith("pain"):
        return "INITIATED"
    if message_version and message_version.startswith("pacs.008"):
        return "INTERBANK_TRANSFER"
    if message_version and message_version.startswith("pacs.009"):
        return "FI_TRANSFER"
    if message_version and message_version.startswith("pacs.002"):
        mapping = {
            "ACCEPTED": "ACCEPTED",
            "REJECTED": "REJECTED",
            "PENDING": "PENDING",
            "PROCESSING": "PROCESSING",
            "PARTIALLY_ACCEPTED": "PROCESSING",
        }
        return mapping.get(normalized_status or "", "STATUS_RECEIVED")
    return "STATUS_RECEIVED"


async def _find_lifecycle(
    session: AsyncSession, org: str, profile: CorrelationProfile
) -> PaymentLifecycleRow | None:
    conds = []
    if profile.original_message_id:
        conds.append(PaymentLifecycleRow.original_message_id == profile.original_message_id)
    if profile.transaction_id:
        conds.append(PaymentLifecycleRow.transaction_id == profile.transaction_id)
    if profile.end_to_end_id:
        conds.append(PaymentLifecycleRow.end_to_end_id == profile.end_to_end_id)
    if profile.instruction_id:
        conds.append(PaymentLifecycleRow.instruction_id == profile.instruction_id)
    if not conds:
        return None
    from sqlalchemy import or_

    result = await session.execute(
        select(PaymentLifecycleRow).where(PaymentLifecycleRow.organization_id == org, or_(*conds))
    )
    return result.scalars().first()


def _profile_from_lifecycle(lifecycle: PaymentLifecycleRow) -> CorrelationProfile:
    return CorrelationProfile(
        original_message_id=lifecycle.original_message_id,
        instruction_id=lifecycle.instruction_id,
        end_to_end_id=lifecycle.end_to_end_id,
        transaction_id=lifecycle.transaction_id,
        amount=lifecycle.amount_minor,
        currency=lifecycle.currency,
        debtor_account=lifecycle.debtor_account,
        creditor_account=lifecycle.creditor_account,
    )


def _profile_from_dict(data: dict[str, Any]) -> CorrelationProfile:
    return CorrelationProfile(
        message_id=data.get("message_id"),
        original_message_id=data.get("original_message_id"),
        instruction_id=data.get("instruction_id"),
        end_to_end_id=data.get("end_to_end_id"),
        transaction_id=data.get("transaction_id"),
        amount=data.get("amount"),
        currency=data.get("currency"),
        reference=data.get("reference"),
        account=data.get("account"),
    )


async def _add_event(
    session: AsyncSession,
    org: str,
    lifecycle: PaymentLifecycleRow,
    result: IsoAnalysisResult,
    iso_row: IsoMessage,
    event_type: str,
    correlation: Any,
) -> None:
    reasons: list[dict[str, object]] = []
    evidence = result.correlation_evidence or (
        list(getattr(correlation, "evidence", []) or []) if correlation else []
    )
    session.add(
        PaymentLifecycleEventRow(
            organization_id=org,
            lifecycle_id=lifecycle.id,
            event_type=event_type,
            message_family=result.message_family,
            message_definition=result.message_definition,
            message_version=result.message_version,
            message_id=str(iso_row.id),
            timestamp=result.processed_at,
            status=result.normalized_status or "UNKNOWN",
            raw_status_code=result.raw_status,
            reasons=reasons,
            correlation_evidence=evidence,
            source_hash=iso_row.message_hash,
        )
    )
    await session.commit()


async def _update_lifecycle_status(session: AsyncSession, result: IsoAnalysisResult) -> None:
    if not result.lifecycle_id:
        return
    row = await session.get(PaymentLifecycleRow, result.lifecycle_id)
    if row is None:
        return
    if result.normalized_status:
        row.current_status = result.normalized_status
    row.updated_at = datetime.now(UTC)
    await session.commit()
