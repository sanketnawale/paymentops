"""Celery account-reconciliation task.

Runs missing-account-event detection for an organization. Reuses the existing worker service;
no new worker deployment is introduced.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from celery import Celery

logger = logging.getLogger("paymentops_worker.account")


async def _run_account_reconciliation(organization_id: str, window_hours: int) -> dict[str, object]:
    from paymentops_api.db.base import Database
    from paymentops_api.services import account_service
    from paymentops_api.settings import get_settings

    db = Database(get_settings())
    try:
        async for session in db.session():
            flagged = await account_service.detect_missing_account_events(
                session, organization_id, window_hours=window_hours
            )
            return {"organization_id": organization_id, "missing_account_events": flagged}
    finally:
        await db.dispose()
    raise RuntimeError("unreachable")


def make_account_reconcile_task(app: Celery) -> None:
    @app.task(name="paymentops.account_reconcile", bind=True, max_retries=2)  # type: ignore[untyped-decorator]
    def account_reconcile(
        self: Any, organization_id: str, window_hours: int = 48
    ) -> dict[str, object]:
        try:
            return asyncio.run(_run_account_reconciliation(organization_id, window_hours))
        except Exception as exc:  # noqa: BLE001
            logger.exception("account_reconcile_failed org=%s", organization_id)
            raise self.retry(exc=exc, countdown=10) from exc

    return None
