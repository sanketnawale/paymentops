"""POST /api/v1/payments/analyze (LEGACY / development-only).

This endpoint predates Integration Profiles. It is retained for development/demo and is
DISABLED in production. When ``persist=true`` it requires an authenticated API client so any
created case is tenant-scoped; it can no longer create unscoped production data.

The production path is the authenticated, profile-resolved endpoint
``POST /api/v1/integrations/{profile_id}/analyze``.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from paymentops_api.auth import AuthenticatedClient, get_optional_api_client
from paymentops_api.db.base import Database
from paymentops_api.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from paymentops_api.services.analysis_service import AnalysisService

router = APIRouter(tags=["analysis"])


def get_analysis_service(request: Request) -> AnalysisService:
    return AnalysisService(request.app.state.analysis_pipeline)


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    db: Database = request.app.state.db
    async for session in db.session():
        yield session


@router.post("/api/v1/payments/analyze", response_model=AnalyzeResponse)
async def analyze_payment(
    payload: AnalyzeRequest,
    request: Request,
    service: AnalysisService = Depends(get_analysis_service),
    session: AsyncSession = Depends(get_session),
    client: AuthenticatedClient | None = Depends(get_optional_api_client),
) -> AnalyzeResponse:
    settings = request.app.state.settings
    if settings.is_production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Legacy analysis endpoint is disabled in production",
        )

    # Persisting requires an authenticated, tenant-scoped client.
    if payload.persist and client is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to persist analysis",
        )

    return await service.analyze(
        payload,
        session=session if payload.persist else None,
        organization_id=client.organization_id if client else None,
    )
