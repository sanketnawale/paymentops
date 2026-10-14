"""Celery task for asynchronous batch processing (CSV -> mapping -> analysis)."""

from __future__ import annotations

import asyncio

import redis.asyncio as aioredis
from paymentops_api.db.base import Database
from paymentops_api.services.batch_service import process_batch_async

from paymentops_worker.logging import configure_logging
from paymentops_worker.settings import get_settings


def process_batch(job_id: str, redis_key: str) -> str:
    """Entrypoint for the Celery task (sync wrapper around async processing)."""
    configure_logging()
    asyncio.run(_process(job_id, redis_key))
    return job_id


async def _process(job_id: str, redis_key: str) -> None:
    settings = get_settings()
    redis = aioredis.from_url(
        settings.celery_broker_url,
        password=settings.redis_password or None,
        decode_responses=True,
        socket_connect_timeout=2,
    )
    db = Database(settings)
    try:
        async for session in db.session():
            await process_batch_async(session, redis, job_id, redis_key, settings)
    except Exception:
        # The batch remains RUNNING/PARTIAL; a follow-up task can resume it.
        raise
    finally:
        await redis.aclose()  # type: ignore[attr-defined]
        await db.dispose()
