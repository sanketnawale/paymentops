"""Worker entrypoint: start Celery workers.

Run from the worker package directory:
    celery -A paymentops_worker.celery_app:celery worker -l INFO
"""

from paymentops_worker.celery_app import celery  # noqa: F401

__all__ = ["celery"]
