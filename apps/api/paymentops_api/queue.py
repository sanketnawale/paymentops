"""Celery client + Redis accessors for the API (used to enqueue async batch work)."""

from __future__ import annotations

from functools import lru_cache

import redis.asyncio as aioredis
from celery import Celery
from redis.asyncio import Redis

from paymentops_api.settings import Settings, get_settings


@lru_cache
def _celery_client() -> Celery:
    s = get_settings()
    app = Celery(
        "paymentops_api_client",
        broker=s.celery_broker_url,
        backend=s.celery_result_backend,
    )
    app.conf.update(task_default_queue="paymentops")
    return app


def enqueue_process_batch(job_id: str, redis_key: str) -> str:
    """Send the batch-processing task to the worker. Returns the task id."""
    result = _celery_client().send_task("paymentops.process_batch", args=[job_id, redis_key])
    return result.id or ""


def enqueue_reconciliation(run_id: str) -> str:
    """Send the reconciliation task to the worker. Returns the task id."""
    result = _celery_client().send_task("paymentops.reconcile", args=[run_id])
    return result.id or ""


def get_redis(settings: Settings | None = None) -> Redis[str]:
    s = settings or get_settings()
    return aioredis.from_url(
        s.celery_broker_url,
        password=s.redis_password or None,
        decode_responses=True,
        socket_connect_timeout=2,
    )
