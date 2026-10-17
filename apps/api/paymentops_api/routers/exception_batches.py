"""Phase 3A: Bounded Batch Exception Desk API.

Operator-authenticated (via the Next.js proxy) endpoints:

- ``POST /api/v1/exception-batches``                          submit a bounded batch (max 5 items)
- ``GET  /api/v1/exception-batches``                          list batches (tenant-scoped)
- ``GET  /api/v1/exception-batches/{batch_id}``               per-item progress + sandbox state
- ``POST /api/v1/exception-batches/{batch_id}/items/{id}/repair/test``  test support on sandbox
- ``GET  /api/v1/exception-batches/{batch_id}/export``        tenant-authorized JSON review report

This is a wrapper around the working investigation pipeline and is unrelated to the legacy
``/api/v1/batches`` (Celery) module. Synthetic single-transaction inputs only.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from paymentops_api.auth import AuthenticatedClient, get_api_client, get_db
from paymentops_api.db.models import BatchItem, BatchRun, Investigation
from paymentops_api.services import exception_batch_service, repair_service
from paymentops_api.services.exception_batch_service import BATCH_MAX_ITEMS

router = APIRouter(tags=["exception-batches"])


class BatchItemInput(BaseModel):
    xml: str = Field(..., description="ISO 20022 XML (pacs.008.001.08, synthetic only)")
    evidence: dict[str, object] | None = Field(
        default=None, description="Optional supporting-evidence JSON for THIS item only"
    )
    filename: str | None = Field(default=None, description="Display metadata only")


class CreateBatchRequest(BaseModel):
    items: list[BatchItemInput] = Field(
        ..., min_length=1, max_length=BATCH_MAX_ITEMS, description="Up to five items (XML required)"
    )
    idempotency_key: str | None = Field(
        default=None, description="Client key to prevent duplicate submissions"
    )


def _batch_detail(
    batch: BatchRun, items: list[BatchItem], investigations: dict[str, Investigation]
) -> dict[str, Any]:
    return {
        **exception_batch_service.summary(batch, items),
        "items": [
            exception_batch_service.item_public(
                item, investigations.get(item.investigation_id or "")
            )
            for item in items
        ],
        "disclaimer": (
            "Synthetic data only. Batch progress is investigation progress; it is not validation, "
            "sandbox success, or human approval. No payment is executed."
        ),
    }


@router.post("/api/v1/exception-batches", status_code=status.HTTP_201_CREATED)
async def create_exception_batch(
    body: CreateBatchRequest,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    items = [{"xml": i.xml, "evidence": i.evidence, "filename": i.filename} for i in body.items]
    try:
        batch, rows, _created = await exception_batch_service.create_batch(
            session, client.organization_id, items, idempotency_key=body.idempotency_key
        )
    except exception_batch_service.BatchValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    investigations = await exception_batch_service.load_investigations(session, rows)
    return _batch_detail(batch, rows, investigations)


@router.get("/api/v1/exception-batches")
async def list_exception_batches(
    limit: int = 50,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    batches = await exception_batch_service.list_batches(
        session, client.organization_id, limit=limit
    )
    out: list[dict[str, Any]] = []
    for batch in batches:
        items = await exception_batch_service.list_items(session, batch.id)
        out.append(exception_batch_service.summary(batch, items))
    return out


@router.get("/api/v1/exception-batches/{batch_id}")
async def get_exception_batch(
    batch_id: str,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    try:
        batch, items = await exception_batch_service.get_batch(
            session, client.organization_id, batch_id
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="batch not found") from None
    investigations = await exception_batch_service.load_investigations(session, items)
    return _batch_detail(batch, items, investigations)


@router.post("/api/v1/exception-batches/{batch_id}/items/{item_id}/repair/test")
async def test_exception_item_repair(
    batch_id: str,
    item_id: str,
    request: Request,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Test the item's supported proposals on a sandbox copy. The original is never modified."""
    try:
        batch, item = await exception_batch_service.get_item(
            session, client.organization_id, batch_id, item_id
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="batch item not found") from None
    if not item.investigation_id:
        raise HTTPException(status_code=409, detail="item has no investigation to test")
    investigations = await exception_batch_service.load_investigations(session, [item])
    inv = investigations.get(item.investigation_id)
    if inv is None or inv.status != "COMPLETED" or not inv.repair:
        raise HTTPException(
            status_code=409, detail="no completed investigation with a proposal to test"
        )
    inv = await repair_service.test_repair(
        session,
        inv,
        pipeline=request.app.state.analysis_pipeline,
        registry=request.app.state.iso_registry,
    )
    items = await exception_batch_service.list_items(session, batch.id)
    investigations = await exception_batch_service.load_investigations(session, items)
    return _batch_detail(batch, items, investigations)


@router.get("/api/v1/exception-batches/{batch_id}/export")
async def export_exception_batch(
    batch_id: str,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    try:
        return await exception_batch_service.build_export(session, client.organization_id, batch_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="batch not found") from None
