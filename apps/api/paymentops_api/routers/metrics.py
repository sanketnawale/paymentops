"""Prometheus metrics endpoint.

Reuses the existing cluster's Prometheus scraping conventions where present. In Week 1
metrics are emitted but no new Prometheus/Grafana stack is introduced (the cluster has
none yet); the endpoint is ready for a ServiceMonitor later. Labels are low-cardinality.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
