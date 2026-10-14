"""Batch job API (CSV upload -> async processing, tenant-scoped)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from paymentops_api.auth import AuthenticatedClient, get_api_client, get_db
from paymentops_api.db.models import BatchJob
from paymentops_api.queue import enqueue_process_batch, get_redis
from paymentops_api.services import batch_service, integration_service

router = APIRouter(tags=["batches"])


class CreateBatchRequest(BaseModel):
    profile_id: str
    csv: str = Field(..., description="CSV content (header row required)")
    profile_version: int = 1


@router.post("/api/v1/batches", status_code=202)
async def create_batch(
    body: CreateBatchRequest,
    request: Request,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    if len(body.csv.encode("utf-8")) > batch_service.MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="batch file too large")
    try:
        _profile = await integration_service.get_profile(
            session, client.organization_id, body.profile_id
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="profile not found") from None

    try:
        job = await batch_service.create_batch_job(
            session, client.organization_id, body.profile_id, body.profile_version
        )
    except batch_service.BatchLimitError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from None

    redis = get_redis(request.app.state.settings)
    try:
        redis_key = await batch_service.store_input(redis, str(job.id), body.csv)
    finally:
        await redis.aclose()  # type: ignore[attr-defined]

    # Enqueue the async worker task; the API returns immediately.
    enqueue_process_batch(str(job.id), redis_key)
    return {
        "job_id": str(job.id),
        "status": job.status,
        "profile_id": body.profile_id,
        "accepted": True,
    }


@router.get("/api/v1/batches")
async def list_batches(
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    result = await session.execute(
        select(BatchJob)
        .where(BatchJob.organization_id == client.organization_id)
        .order_by(BatchJob.created_at.desc())
    )
    return [_job_to_dict(j) for j in result.scalars().all()]


@router.get("/api/v1/batches/{job_id}")
async def get_batch(
    job_id: str,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        job = await batch_service.get_job(session, client.organization_id, job_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="job not found") from None
    return _job_to_dict(job)


def _job_to_dict(job: BatchJob) -> dict[str, object]:
    return {
        "job_id": str(job.id),
        "profile_id": str(job.profile_id),
        "profile_version": job.profile_version,
        "status": job.status,
        "total_records": job.total_records,
        "processed_records": job.processed_records,
        "ready_count": job.ready_count,
        "repairable_count": job.repairable_count,
        "review_required_count": job.review_required_count,
        "unresolved_count": job.unresolved_count,
        "failed_count": job.failed_count,
        "report": job.report,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
