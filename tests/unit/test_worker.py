"""Unit tests for the worker skeleton (no broker connection required)."""

from __future__ import annotations

from paymentops_worker.celery_app import (
    build_celery,
    health_task,
    smoke_task,
)


def test_celery_app_registers_health_and_smoke_tasks():
    celery = build_celery("redis://localhost:6379/0", "redis://localhost:6379/1")
    assert "paymentops.health" in celery.tasks
    assert "paymentops.smoke" in celery.tasks
    assert "paymentops.process_batch" in celery.tasks
    assert "paymentops.reconcile" in celery.tasks


def test_health_task_returns_ok():
    assert health_task() == "ok"


def test_smoke_task_is_harmless():
    assert smoke_task("pong").startswith("paymentops-worker-ack:")
