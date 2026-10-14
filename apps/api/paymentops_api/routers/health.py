"""Liveness (/health) and readiness (/ready) endpoints.

- /health  : process liveness only. Always reflects the API process being alive.
- /ready   : probes configured dependencies. Returns 503 when a required dependency is down.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from paymentops_api.db.base import Database
from paymentops_api.dependencies import check_dependencies, readiness_body
from paymentops_api.settings import Settings

router = APIRouter(tags=["health"])


def get_db(request: Request) -> Database:
    db: Database = request.app.state.db
    return db


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe")
async def ready(
    request: Request,
    db: Database = Depends(get_db),
) -> JSONResponse:
    settings: Settings = request.app.state.settings
    deps = await check_dependencies(settings, db)
    body = readiness_body(deps)
    ready = body["status"] == "ready"
    return JSONResponse(
        status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=body,
    )
