"""Celery reconciliation task.

Loads a reconciliation run + its source/candidate records, runs deterministic matching, and
updates the run + candidate rows. Tenant-scoped via the run's organization_id.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from celery import Celery

logger = logging.getLogger("paymentops_worker.reconcile")


async def _run_reconciliation(run_id: str) -> dict[str, object]:
    # Imported here to avoid heavy imports at module load and to keep the worker package
    # decoupled from the API app.
    from paymentops_api.db.base import Database
    from paymentops_api.db.models import MatchRun
    from paymentops_api.services import matching_service
    from paymentops_api.settings import get_settings

    settings = get_settings()
    db = Database(settings)

    try:
        async for session in db.session():
            run = await session.get(MatchRun, run_id)
            if run is None:
                raise LookupError(f"reconciliation run not found: {run_id}")
            org = str(run.organization_id)
            source_ids = _as_strings((run.source_dataset or {}).get("record_ids", []))
            cand_ids = _as_strings((run.candidate_dataset or {}).get("record_ids", []))

            source_records = [
                matching_service._row_to_domain(r)
                for r in await _load_records(session, org, source_ids)
            ]
            candidate_records = [
                matching_service._row_to_domain(r)
                for r in await _load_records(session, org, cand_ids)
            ]

            policy = await matching_service.get_published_policy(
                session, org, str(run.policy_id) if run.policy_id else None
            )
            completed = await matching_service.execute_reconciliation(
                session,
                org,
                run_id,
                source_records=source_records,
                candidate_records=candidate_records,
                policy=policy,
            )
            return {"run_id": run_id, "status": completed.status, "report": completed.report}
    finally:
        await db.dispose()
    raise RuntimeError("unreachable")


def _as_strings(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


async def _load_records(session: Any, org: str, ids: list[str]) -> list[Any]:
    from paymentops_api.db.models import MatchRecordRow
    from sqlalchemy import select

    result = await session.execute(
        select(MatchRecordRow).where(
            MatchRecordRow.organization_id == org,
            MatchRecordRow.record_id.in_(ids),
        )
    )
    return list(result.scalars().all())


def make_reconcile_task(app: Celery) -> None:
    @app.task(name="paymentops.reconcile", bind=True, max_retries=2)  # type: ignore[untyped-decorator]
    def reconcile(self: Any, run_id: str) -> dict[str, object]:
        try:
            return asyncio.run(_run_reconciliation(run_id))
        except LookupError:
            logger.warning("reconcile_run_not_found run_id=%s", run_id)
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("reconcile_run_failed run_id=%s", run_id)
            raise self.retry(exc=exc, countdown=10) from exc

    return None
