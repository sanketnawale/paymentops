"""Batch processing service (CSV streaming, defensive limits, tenant-scoped).

The API creates a job and stores the CSV input in Redis; the worker task
``paymentops.process_batch`` reads it and processes records asynchronously. Progress is
updated at configurable intervals. Per-record failures are isolated.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import UTC, datetime
from typing import cast

from paymentops_api.db.models import BatchJob
from paymentops_api.db.models import IntegrationProfile as ProfileRow
from paymentops_api.services.integration_analysis_service import analyze_profile
from paymentops_api.settings import Settings
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from integration_profiles.models import InputFormat, IntegrationProfile
from mapping_engine.models import MappingDefinition
from rules_engine.declarative import RuleConfig

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 2_000_000
MAX_ROWS = 5_000
# Update progress in the DB every N rows.
PROGRESS_INTERVAL = 25
# Redis key TTL for stored CSV input.
INPUT_TTL_SECONDS = 3600


class BatchLimitError(ValueError):
    pass


async def create_batch_job(
    session: AsyncSession,
    organization_id: str,
    profile_id: str,
    profile_version: int,
) -> BatchJob:
    row = BatchJob(
        organization_id=organization_id,
        profile_id=profile_id,
        profile_version=profile_version,
        status="QUEUED",
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def store_input(redis: Redis[str], job_id: str, csv_text: str) -> str:
    """Store the CSV input in Redis under a TTL'd key; returns the key."""
    key = f"paymentops:batch:{job_id}:input"
    await redis.set(key, csv_text, ex=INPUT_TTL_SECONDS)
    return key


async def get_input(redis: Redis[str], key: str) -> str:
    value = await redis.get(key)
    if value is None:
        raise LookupError("batch input not found")
    if isinstance(value, bytes):
        return str(value).decode("utf-8")
    return str(value)


async def process_batch_async(
    session: AsyncSession,
    redis: Redis[str],
    job_id: str,
    redis_key: str,
    settings: Settings,
) -> dict[str, object]:
    """Stream a CSV, map + analyze each record, update counters at intervals."""
    job = await _get_row(session, job_id)
    # Idempotency: a completed/partial/failed job is not reprocessed.
    if job.status in ("COMPLETED", "PARTIAL", "FAILED"):
        return job.report or {}

    csv_text = await get_input(redis, redis_key)
    if len(csv_text.encode("utf-8")) > MAX_FILE_BYTES:
        job.status = "FAILED"
        await session.commit()
        raise BatchLimitError("batch file too large")
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    if len(rows) > MAX_ROWS:
        job.status = "FAILED"
        await session.commit()
        raise BatchLimitError("too many rows")

    counts = {"READY": 0, "REPAIRABLE": 0, "REVIEW_REQUIRED": 0, "UNRESOLVED": 0}
    failed = 0
    top_rules: dict[str, int] = {}
    job.status = "RUNNING"
    job.started_at = datetime.now(UTC)
    job.total_records = len(rows)
    await session.commit()

    profile = await _load_profile(session, job)
    for i, row in enumerate(rows):
        try:
            csv_text_row = "\n".join([",".join(row.keys()), ",".join(row.values())])
            result = analyze_profile(profile, csv_text_row.encode("utf-8"), settings=settings)
            status = str(result.get("address_readiness") or "UNRESOLVED")
            counts[status] = counts.get(status, 0) + 1
            for finding in cast(list[object], result.get("rule_findings") or []):
                rule_id = str(cast(dict[str, object], finding).get("rule_id"))
                top_rules[rule_id] = top_rules.get(rule_id, 0) + 1
        except Exception:  # noqa: BLE001 - per-record isolation
            failed += 1

        job.processed_records = i + 1
        if (i + 1) % PROGRESS_INTERVAL == 0 or (i + 1) == len(rows):
            _write_counts(job, counts, failed, len(rows), top_rules)
            await session.commit()

    job.status = "COMPLETED" if failed == 0 else "PARTIAL"
    job.completed_at = datetime.now(UTC)
    _write_counts(job, counts, failed, len(rows), top_rules)
    await session.commit()

    try:
        await redis.delete(redis_key)
    except Exception:  # noqa: BLE001
        logger.warning("batch_input_cleanup_failed: %s", job_id)
    return job.report or {}


def _write_counts(
    job: BatchJob, counts: dict[str, int], failed: int, total: int, top_rules: dict[str, int]
) -> None:
    job.ready_count = counts.get("READY", 0)
    job.repairable_count = counts.get("REPAIRABLE", 0)
    job.review_required_count = counts.get("REVIEW_REQUIRED", 0)
    job.unresolved_count = counts.get("UNRESOLVED", 0)
    job.failed_count = failed
    job.report = {
        "total_records": total,
        "ready": counts.get("READY", 0),
        "repairable": counts.get("REPAIRABLE", 0),
        "review_required": counts.get("REVIEW_REQUIRED", 0),
        "unresolved": counts.get("UNRESOLVED", 0),
        "failed": failed,
        "top_rule_findings": sorted(top_rules.items(), key=lambda x: -x[1])[:10],
    }


async def _load_profile(session: AsyncSession, job: BatchJob) -> IntegrationProfile:
    result = await session.execute(select(ProfileRow).where(ProfileRow.id == job.profile_id))
    row = result.scalar_one()
    mapping = MappingDefinition.model_validate(row.mapping)
    rules = [RuleConfig.from_dict(r) for r in (row.rules or [])]
    return IntegrationProfile(
        id=str(row.id),
        organization_id=str(row.organization_id),
        name=row.name,
        input_format=InputFormat(row.input_format),
        status=row.status,
        mapping=mapping,
        rules=rules,
        version_number=row.version_number,
        address_policy=row.address_policy,
    )


async def _get_row(session: AsyncSession, job_id: str) -> BatchJob:
    result = await session.execute(select(BatchJob).where(BatchJob.id == job_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise LookupError("job not found")
    return row


async def get_job(session: AsyncSession, organization_id: str, job_id: str) -> BatchJob:
    result = await session.execute(
        select(BatchJob).where(BatchJob.id == job_id, BatchJob.organization_id == organization_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise LookupError("job not found")
    return row
