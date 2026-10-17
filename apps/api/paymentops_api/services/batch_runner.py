"""Phase 3A: durable batch runner.

Advances the Batch Exception Desk server-side (never from browser polling, never as a
fire-and-forget request task). State lives in the database; a restart resumes unfinished work
without duplicating external runs.

Design choice: reuse the existing API component and its Postgres database instead of deploying a
new worker/broker. The runner is a single supervised asyncio task started in the app lifespan and
uses a claim column (``claimed_until``) plus a ``STARTING`` marker so:
- items are processed one model investigation at a time (shared AMD/Evolus key), and
- a workflow start is never retried blindly: a ``STARTING`` item found after a restart is marked
  failed as *ambiguous* rather than restarted.
"""

from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from paymentops_api.db.base import Database
from paymentops_api.db.models import BatchItem, BatchRun, Investigation
from paymentops_api.evolus import EvolusClient
from paymentops_api.logging import get_logger
from paymentops_api.services import exception_batch_service, investigation_service
from paymentops_api.settings import Settings
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from analysis.pipeline import AnalysisPipeline
from iso_engine.registry import IsoMessageRegistry

logger = get_logger("paymentops.batch_runner")

CLAIM_SECONDS = 300.0
IDLE_SECONDS = 3.0
BUSY_SECONDS = 0.25
_TERMINAL_FOR_BATCH = {"COMPLETED", "FAILED", "REJECTED"}


async def recover_interrupted_starts(session: AsyncSession) -> int:
    """Mark items left mid-start by a restart as failed-ambiguous (never re-start them)."""
    result = await session.execute(
        update(BatchItem)
        .where(BatchItem.status == "STARTING")
        .values(
            status="FAILED",
            error=(
                "Ambiguous workflow start (process restarted mid-start); not retried to avoid "
                "a duplicate external run. Investigate manually and resubmit as a new item."
            ),
            claimed_until=None,
            updated_at=datetime.now(UTC),
        )
    )
    await session.commit()
    count = int(getattr(result, "rowcount", 0) or 0)
    if count:
        logger.warning("batch_items_ambiguous_start", count=count)
    return count


async def _claim(session: AsyncSession, statuses: list[str]) -> BatchItem | None:
    now = datetime.now(UTC)
    subq = (
        select(BatchItem.id)
        .where(
            BatchItem.status.in_(statuses),
            or_(BatchItem.claimed_until.is_(None), BatchItem.claimed_until < now),
        )
        .order_by(BatchItem.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    stmt = (
        update(BatchItem)
        .where(BatchItem.id == subq)
        .values(claimed_until=now + timedelta(seconds=CLAIM_SECONDS))
        .returning(BatchItem.id)
    )
    row = (await session.execute(stmt)).first()
    await session.commit()
    if row is None:
        return None
    return await session.get(BatchItem, row[0])


async def _sync_batch_status(session: AsyncSession, batch_pk: UUID) -> None:
    batch = await session.get(BatchRun, batch_pk)
    if batch is None:
        return
    result = await session.execute(select(BatchItem.status).where(BatchItem.batch_id == batch_pk))
    statuses = [row[0] for row in result.all()]
    if not statuses:
        new_status = "PENDING"
    elif any(s not in _TERMINAL_FOR_BATCH for s in statuses):
        new_status = "RUNNING"
    elif all(s == "COMPLETED" for s in statuses):
        new_status = "COMPLETED"
    elif any(s == "COMPLETED" for s in statuses):
        new_status = "PARTIAL"
    else:
        new_status = "FAILED"

    terminal = new_status in {"COMPLETED", "PARTIAL", "FAILED"}
    if new_status != batch.status or (terminal and batch.completed_at is None):
        batch.status = new_status
        batch.updated_at = datetime.now(UTC)
        if terminal:
            batch.completed_at = datetime.now(UTC)
        await session.commit()


async def _start_item(
    session: AsyncSession,
    item: BatchItem,
    *,
    settings: Settings,
    pipeline: AnalysisPipeline,
    registry: IsoMessageRegistry,
    evolus_client: EvolusClient,
) -> None:
    now = datetime.now(UTC)
    xml_bytes = base64.b64decode(item.payload_xml or "")
    try:
        inv = await investigation_service.start_uploaded_investigation(
            session,
            str(item.organization_id),
            xml_bytes,
            item.payload_evidence,
            settings=settings,
            pipeline=pipeline,
            registry=registry,
            evolus_client=evolus_client,
            start_workflow=False,
        )
    except Exception as exc:  # noqa: BLE001
        item.status = "FAILED"
        item.error = exception_batch_service.reject_reason(exc)
        item.claimed_until = None
        item.updated_at = now
        await session.commit()
        return

    # Persist the investigation link and the STARTING marker BEFORE the external call, so a
    # restart can recognise an ambiguous start instead of firing a duplicate run.
    item.investigation_id = inv.investigation_id
    item.status = "STARTING"
    item.start_attempted_at = now
    item.updated_at = now
    await session.commit()

    try:
        await investigation_service.start_workflow_for_investigation(
            session, inv, settings=settings, client=evolus_client
        )
        await session.refresh(inv)
    except Exception as exc:  # noqa: BLE001
        item.status = "FAILED"
        item.error = f"workflow start error ({type(exc).__name__})"
        item.claimed_until = None
        item.updated_at = now
        await session.commit()
        return

    if inv.status == "FAILED":
        item.status = "FAILED"
        item.error = inv.error or "the Evolus workflow failed to start"
    else:
        item.status = "RUNNING"
        item.evolus_execution_id = inv.evolus_execution_id
    item.claimed_until = None
    item.updated_at = now
    await session.commit()


async def _poll_item(
    session: AsyncSession, item: BatchItem, *, evolus_client: EvolusClient
) -> None:
    now = datetime.now(UTC)
    result = await session.execute(
        select(Investigation).where(
            Investigation.investigation_id == item.investigation_id,
            Investigation.organization_id == item.organization_id,
        )
    )
    inv = result.scalar_one_or_none()
    if inv is None:
        item.status = "FAILED"
        item.error = "linked investigation not found"
        item.claimed_until = None
        item.updated_at = now
        await session.commit()
        return
    inv = await investigation_service.refresh_investigation(session, inv, client=evolus_client)
    if inv.status == "COMPLETED":
        item.status = "COMPLETED"
    elif inv.status == "FAILED":
        item.status = "FAILED"
        item.error = inv.error
    item.claimed_until = None
    item.updated_at = now
    await session.commit()


async def process_once(
    session: AsyncSession,
    *,
    settings: Settings,
    pipeline: AnalysisPipeline,
    registry: IsoMessageRegistry,
    evolus_client: EvolusClient,
) -> bool:
    """Advance the queue by one step. Returns True if any work was performed.

    Strictly sequential: while any item is RUNNING we only poll it; a new workflow is started
    only when nothing is RUNNING. This respects the shared Evolus/AMD key.
    """
    running = await _claim(session, ["RUNNING"])
    if running is not None:
        await _poll_item(session, running, evolus_client=evolus_client)
        await _sync_batch_status(session, running.batch_id)
        return True

    pending = await _claim(session, ["PENDING"])
    if pending is not None:
        await _start_item(
            session,
            pending,
            settings=settings,
            pipeline=pipeline,
            registry=registry,
            evolus_client=evolus_client,
        )
        await _sync_batch_status(session, pending.batch_id)
        return True
    return False


async def run_loop(app: Any, *, poll_seconds: float = IDLE_SECONDS) -> None:
    """Supervised background loop. Started once in the app lifespan; cancelled on shutdown."""
    settings: Settings = app.state.settings
    pipeline: AnalysisPipeline = app.state.analysis_pipeline
    registry: IsoMessageRegistry = app.state.iso_registry
    evolus_client: EvolusClient = app.state.evolus_client
    db: Database = app.state.db

    async with db.session_factory() as session:
        await recover_interrupted_starts(session)
    logger.info("batch_runner_started")

    while True:
        did_work = False
        try:
            async with db.session_factory() as session:
                did_work = await process_once(
                    session,
                    settings=settings,
                    pipeline=pipeline,
                    registry=registry,
                    evolus_client=evolus_client,
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - the loop must survive transient failures
            logger.warning("batch_runner_tick_failed", error=type(exc).__name__)
        await asyncio.sleep(BUSY_SECONDS if did_work else poll_seconds)
