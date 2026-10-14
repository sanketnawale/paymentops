"""System info endpoint (/api/v1/info).

Exposes only non-sensitive metadata: product name, version, environment, AI state and
readiness posture. It must never surface credentials or internal connection details.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from paymentops_api.settings import Settings

router = APIRouter(tags=["info"])


@router.get("/api/v1/info", summary="Public non-sensitive platform info")
async def info(request: Request) -> dict[str, object]:
    settings: Settings = request.app.state.settings
    return settings.safe_info()
