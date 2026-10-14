"""Internal address-structuring service.

Exposes an internal-only HTTP interface around the upstream Swift address-structuring engine.
It is NOT exposed publicly. Town/country inference requires the reference data mounted at
``/resources``; otherwise ``/ready`` reports not-ready and the caller falls back.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from service.provider import ProviderNotReadyError, SwiftStructureProvider

app = FastAPI(title="paymentops-address-structuring", version="0.1.0")
_provider = SwiftStructureProvider()


class StructureRequest(BaseModel):
    text: str = Field(..., min_length=1)
    suggested_country: str | None = None
    force: bool = False


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, object]:
    if not _provider.ready:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": _provider.reason},
        )
    return {"status": "ready"}


@app.post("/structure")
async def structure(req: StructureRequest) -> dict[str, object]:
    if not _provider.ready:
        raise HTTPException(status_code=503, detail="address-structuring provider not ready")
    try:
        result = _provider.structure(
            req.text,
            suggested_country=req.suggested_country,
            force=req.force,
        )
    except ProviderNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - never leak internal details
        raise HTTPException(status_code=500, detail="inference failed") from exc
    return result.to_dict()
