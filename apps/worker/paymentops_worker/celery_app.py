"""Celery application for PaymentOps background processing.

Broker/result backend come from structured settings (never hard-coded). In Week 1 only a
health/smoke task is registered — no fake business jobs. The worker is structured for
future Redis/Celery tasks that will run deterministic validation, mapping, etc.
"""

from __future__ import annotations

from celery import Celery
from paymentops_api.settings import Settings

from paymentops_worker.logging import configure_logging

# Lazily resolved to avoid importing settings at module import time in non-worker contexts.
_config: dict[str, str] = {}


def build_celery(broker_url: str, result_backend: str) -> Celery:
    app = Celery(
        "paymentops_worker",
        broker=broker_url,
        backend=result_backend,
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_default_queue="paymentops",
        broker_connection_retry_on_startup=True,
        result_expires=3600,
    )
    app.task(name="paymentops.health")(health_task)
    app.task(name="paymentops.smoke")(smoke_task)
    # Async batch processing task (imported lazily to avoid heavy imports at module load).
    from paymentops_worker.batch_tasks import process_batch

    app.task(name="paymentops.process_batch")(process_batch)
    # Async reconciliation task.
    from paymentops_worker.reconciliation_tasks import make_reconcile_task

    make_reconcile_task(app)
    # Async account-reconciliation task (Week 6).
    from paymentops_worker.account_tasks import make_account_reconcile_task

    make_account_reconcile_task(app)
    return app


def _settings() -> Settings:
    from paymentops_worker.settings import get_settings

    return get_settings()


def get_celery() -> Celery:
    """Module-level accessor used by worker entrypoints (resolution on first call)."""
    return build_celery(_settings().celery_broker_url, _settings().celery_result_backend)


def health_task() -> str:
    """Idempotent health task used to verify worker operation."""
    return "ok"


def smoke_task(message: str = "hello") -> str:
    """Minimal end-to-end task. Does not touch financial data."""
    configure_logging()
    return f"paymentops-worker-ack:{message}"


# Instantiated last so the task functions above are defined when tasks are registered.
celery = get_celery()
