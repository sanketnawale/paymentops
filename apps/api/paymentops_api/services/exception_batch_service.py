"""Phase 3A: bounded Batch Exception Desk service.

A thin, tenant-scoped wrapper around the working single-file investigation pipeline. It validates
and stores batch/item records but does NOT itself start Evolus runs or advance work (the durable
runner in ``batch_runner`` does that, one model investigation at a time). The legacy Celery batch
module (``routers/batches.py``) is unrelated and untouched.

Safety:
- Synthetic inputs only; the existing size/parser/security limits are reused unchanged.
- No ZIP, no multi-transaction messages, no MCP, no new agent.
- Filenames are display metadata only and are never used as storage paths.
- No credentials, secrets or raw model reasoning are stored or exported.
"""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from paymentops_api.db.models import BatchItem, BatchRun, Investigation
from paymentops_api.logging import get_logger
from paymentops_api.services import investigation_service
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("paymentops.batch")

BATCH_MAX_ITEMS = 5
_TERMINAL_ITEM_STATUSES = {"COMPLETED", "FAILED", "REJECTED"}


class BatchValidationError(Exception):
    """Raised when a batch submission is invalid (safe to surface to the operator)."""


def new_batch_id() -> str:
    return f"bat-{uuid.uuid4().hex[:12]}"


def new_item_id() -> str:
    return f"bit-{uuid.uuid4().hex[:12]}"


def org_uuid(org: str | uuid.UUID) -> uuid.UUID:
    return org if isinstance(org, uuid.UUID) else uuid.UUID(str(org))


def evidence_hash(evidence: dict[str, Any] | None) -> str | None:
    if evidence is None:
        return None
    payload = json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def reject_reason(exc: Exception) -> str:
    """A safe, non-payload-echoing rejection reason for an invalid item."""
    if isinstance(exc, investigation_service.UploadValidationError):
        return str(exc)[:300]
    return f"rejected ({type(exc).__name__}): {str(exc)[:240]}"


# --------------------------------------------------------------------------- create


async def _find_by_idempotency(
    session: AsyncSession, org: uuid.UUID, idempotency_key: str
) -> BatchRun | None:
    result = await session.execute(
        select(BatchRun).where(
            BatchRun.organization_id == org,
            BatchRun.idempotency_key == idempotency_key,
        )
    )
    return result.scalar_one_or_none()


async def create_batch(
    session: AsyncSession,
    org: str | uuid.UUID,
    items: list[dict[str, Any]],
    *,
    idempotency_key: str | None = None,
) -> tuple[BatchRun, list[BatchItem], bool]:
    """Create a batch. Returns ``(batch, items, created)``.

    ``items`` are dicts ``{"xml": str, "evidence": dict | None, "filename": str | None}``. Each
    item is validated independently: an invalid item is stored as ``REJECTED`` and does not block
    the others. A repeated ``idempotency_key`` returns the original batch (no duplicate work).
    """
    if not items:
        raise BatchValidationError("At least one item is required.")
    if len(items) > BATCH_MAX_ITEMS:
        raise BatchValidationError(f"At most {BATCH_MAX_ITEMS} items are allowed per batch.")
    key = (idempotency_key or "").strip()[:128] or None
    org_id = org_uuid(org)

    if key is not None:
        existing = await _find_by_idempotency(session, org_id, key)
        if existing is not None:
            existing_items = await list_items(session, existing.id)
            return existing, existing_items, False

    batch = BatchRun(
        batch_id=new_batch_id(),
        organization_id=org_id,
        idempotency_key=key,
        status="PENDING",
        total_items=len(items),
        created_at=datetime.now(UTC),
    )
    session.add(batch)
    await session.flush()

    rows: list[BatchItem] = []
    for index, item in enumerate(items):
        xml_bytes = (item.get("xml") or "").encode("utf-8")
        evidence = item.get("evidence")
        display = (item.get("filename") or "").strip()[:255] or None
        row = BatchItem(
            item_id=new_item_id(),
            batch_id=batch.id,
            organization_id=org_id,
            item_index=index,
            display_filename=display,
            input_hash=investigation_service.payload_sha256(xml_bytes),
            evidence_hash=evidence_hash(evidence),
            status="PENDING",
            created_at=datetime.now(UTC),
        )
        try:
            investigation_service.validate_uploaded_case(xml_bytes, evidence)
        except Exception as exc:  # noqa: BLE001 - per-item isolation is intentional
            row.status = "REJECTED"
            row.error = reject_reason(exc)
        else:
            row.payload_xml = base64.b64encode(xml_bytes).decode("ascii")
            row.payload_evidence = evidence
        session.add(row)
        rows.append(row)

    batch.total_items = len(rows)
    await session.commit()
    await session.refresh(batch)
    for row in rows:
        await session.refresh(row)
    logger.info(
        "batch_created",
        batch_id=batch.batch_id,
        items=len(rows),
        rejected=sum(1 for r in rows if r.status == "REJECTED"),
    )
    return batch, rows, True


# --------------------------------------------------------------------------- reads


async def list_items(session: AsyncSession, batch_pk: uuid.UUID) -> list[BatchItem]:
    result = await session.execute(
        select(BatchItem).where(BatchItem.batch_id == batch_pk).order_by(BatchItem.item_index)
    )
    return list(result.scalars().all())


async def list_batches(
    session: AsyncSession, org: str | uuid.UUID, limit: int = 50
) -> list[BatchRun]:
    limit = max(1, min(limit, 200))
    result = await session.execute(
        select(BatchRun)
        .where(BatchRun.organization_id == org_uuid(org))
        .order_by(BatchRun.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_batch(
    session: AsyncSession, org: str | uuid.UUID, batch_id: str
) -> tuple[BatchRun, list[BatchItem]]:
    result = await session.execute(
        select(BatchRun).where(
            BatchRun.batch_id == batch_id,
            BatchRun.organization_id == org_uuid(org),
        )
    )
    batch = result.scalar_one_or_none()
    if batch is None:
        raise LookupError(batch_id)
    return batch, await list_items(session, batch.id)


async def get_item(
    session: AsyncSession, org: str | uuid.UUID, batch_id: str, item_id: str
) -> tuple[BatchRun, BatchItem]:
    fetch_batch, items = await get_batch(session, org, batch_id)
    for item in items:
        if item.item_id == item_id:
            return fetch_batch, item
    raise LookupError(item_id)


async def counts_by_batch(session: AsyncSession, batch_pk: uuid.UUID) -> dict[str, int]:
    result = await session.execute(
        select(BatchItem.status, func.count())
        .where(BatchItem.batch_id == batch_pk)
        .group_by(BatchItem.status)
    )
    return dict(result.all())


def is_terminal(status: str) -> bool:
    return status in _TERMINAL_ITEM_STATUSES


async def load_investigations(
    session: AsyncSession, items: list[BatchItem]
) -> dict[str, Investigation]:
    ids = [i.investigation_id for i in items if i.investigation_id]
    if not ids:
        return {}
    result = await session.execute(
        select(Investigation).where(Investigation.investigation_id.in_(ids))
    )
    return {inv.investigation_id: inv for inv in result.scalars().all()}


# --------------------------------------------------------------------------- serializers


def summary(batch: BatchRun, items: list[BatchItem]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    return {
        "batch_id": batch.batch_id,
        "status": batch.status,
        "total_items": batch.total_items,
        "counts": counts,
        "completed": counts.get("COMPLETED", 0),
        "failed": counts.get("FAILED", 0),
        "rejected": counts.get("REJECTED", 0),
        "pending": counts.get("PENDING", 0) + counts.get("STARTING", 0) + counts.get("RUNNING", 0),
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "updated_at": batch.updated_at.isoformat() if batch.updated_at else None,
        "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
    }


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def item_public(item: BatchItem, inv: Investigation | None) -> dict[str, Any]:
    """Item view: batch progress + linked investigation state (no payload bytes, no secrets)."""
    detail: dict[str, Any] = {
        "item_id": item.item_id,
        "item_index": item.item_index,
        "display_filename": item.display_filename,
        "status": item.status,
        "error": item.error,
        "input_hash": item.input_hash,
        "evidence_hash": item.evidence_hash,
        "investigation_id": item.investigation_id,
        "evolus_execution_id": item.evolus_execution_id,
        "investigation_status": inv.status if inv is not None else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }
    if inv is None:
        return detail
    repair = _as_dict(inv.repair)
    record = _as_dict(inv.supporting_record)
    proposal = _as_dict(repair.get("proposal"))
    server_validation = _as_dict(proposal.get("server_validation"))
    sandbox = _as_dict(repair.get("test"))
    findings = _as_list(_as_dict(inv.deterministic_findings).get("rule_findings"))

    def sget(key: str) -> Any:
        return sandbox.get(key) if sandbox else None

    detail.update(
        {
            "evidence_refs": [e.get("ref") for e in _as_list(record.get("entries"))],
            "original_findings": findings,
            "repair_status": repair.get("status"),
            "proposed_changes": _as_list(server_validation.get("allowed")),
            "rejected_changes": _as_list(server_validation.get("rejected")),
            "sandbox": {
                "sandbox_id": sget("sandbox_id"),
                "original_hash": sget("original_hash"),
                "sandbox_hash": sget("sandbox_hash"),
                "review_status": sandbox.get("review_status"),
                "xsd_valid": sandbox.get("xsd_valid"),
                "before_findings": sandbox.get("before_findings"),
                "after_findings": sandbox.get("after_findings"),
                "applied_changes": sandbox.get("applied_changes"),
                "unresolved_findings": sandbox.get("unresolved_findings"),
                "tested_at": sandbox.get("tested_at"),
            }
            if sandbox
            else None,
            "remaining_findings": sandbox.get("after_findings") if sandbox else None,
            "unresolved_findings": sandbox.get("unresolved_findings") if sandbox else None,
        }
    )
    return detail


# --------------------------------------------------------------------------- review export


async def build_export(
    session: AsyncSession, org: str | uuid.UUID, batch_id: str
) -> dict[str, Any]:
    """Tenant-authorized JSON review report (synthetic only; no secrets/model reasoning)."""
    batch, items = await get_batch(session, org, batch_id)
    investigations = await load_investigations(session, items)
    exported_items: list[dict[str, Any]] = []
    for item in items:
        inv = investigations.get(item.investigation_id or "")
        record = _as_dict(inv.supporting_record) if inv is not None else {}
        repair = _as_dict(inv.repair) if inv is not None else {}
        proposal = _as_dict(repair.get("proposal"))
        server_validation = _as_dict(proposal.get("server_validation"))
        sandbox = _as_dict(repair.get("test"))
        findings = (
            _as_list(_as_dict(inv.deterministic_findings).get("rule_findings"))
            if inv is not None
            else []
        )
        exported_items.append(
            {
                "item_id": item.item_id,
                "item_index": item.item_index,
                "display_filename": item.display_filename,
                "status": item.status,
                "error": item.error,
                "input_hash": item.input_hash,
                "evidence_hash": item.evidence_hash,
                "investigation_id": item.investigation_id,
                "evolus_execution_id": item.evolus_execution_id,
                "evidence_refs": [e.get("ref") for e in _as_list(record.get("entries"))],
                "supporting_record_gaps": _as_list(record.get("gaps")),
                "original_findings": findings,
                # Proposed (not executed) changes.
                "proposed_changes": _as_list(server_validation.get("allowed")),
                "rejected_changes": _as_list(server_validation.get("rejected")),
                "sandbox_tested": bool(sandbox),
                "before_findings": sandbox.get("before_findings") if sandbox else None,
                "after_findings": sandbox.get("after_findings") if sandbox else None,
                "applied_changes": sandbox.get("applied_changes") if sandbox else None,
                "unresolved_issues": sandbox.get("unresolved_findings") if sandbox else None,
                "original_hash": sandbox.get("original_hash") if sandbox else item.input_hash,
                "sandbox_hash": sandbox.get("sandbox_hash") if sandbox else None,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            }
        )
    return {
        "report": "paymentops.batch_exception_review",
        "synthetic": True,
        "generated_at": datetime.now(UTC).isoformat(),
        "batch": summary(batch, items),
        "items": exported_items,
        "notes": [
            "Synthetic data only; no real payment data is present.",
            "proposed_changes are proposals; applied_changes are sandbox-only test results.",
            "A completed workflow is investigation progress, not validation or human approval.",
        ],
        "disclaimer": (
            "Proposed changes are tested on sandbox copies of the synthetic input; the original "
            "payload is never modified and no payment is executed, authorized or settled."
        ),
    }
