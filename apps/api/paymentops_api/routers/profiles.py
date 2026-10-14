"""Integration Profile management API (tenant-scoped via the authenticated client)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from integration_profiles.models import IntegrationProfile
from paymentops_api.auth import AuthenticatedClient, get_api_client, get_db
from paymentops_api.db.models import IntegrationProfile as ProfileRow
from paymentops_api.services import integration_service

router = APIRouter(tags=["integration-profiles"])


@router.post("/api/v1/integration-profiles", status_code=201)
async def create_profile(
    profile: IntegrationProfile,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> IntegrationProfile:
    return await integration_service.create_profile(session, client.organization_id, profile)


@router.get("/api/v1/integration-profiles")
async def list_profiles(
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> list[IntegrationProfile]:
    result = await session.execute(
        select(ProfileRow).where(ProfileRow.organization_id == client.organization_id)
    )
    return [integration_service._to_domain(r) for r in result.scalars().all()]


@router.get("/api/v1/integration-profiles/{profile_id}")
async def get_profile(
    profile_id: str,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> IntegrationProfile:
    try:
        return await integration_service.get_profile(session, client.organization_id, profile_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="profile not found") from None


@router.put("/api/v1/integration-profiles/{profile_id}")
async def update_profile(
    profile_id: str,
    profile: IntegrationProfile,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> IntegrationProfile:
    try:
        return await integration_service.update_profile(
            session, client.organization_id, profile_id, profile
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="profile not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.post("/api/v1/integration-profiles/{profile_id}/validate")
async def validate_profile(
    profile_id: str,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        profile = await integration_service.get_profile(session, client.organization_id, profile_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="profile not found") from None
    errors = integration_service.validate_profile(profile)
    return {"valid": not errors, "errors": errors, "warnings": []}


@router.post("/api/v1/integration-profiles/{profile_id}/test")
async def test_profile(
    profile_id: str,
    request: Request,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    from paymentops_api.services.integration_analysis_service import analyze_profile

    try:
        profile = await integration_service.get_profile(session, client.organization_id, profile_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="profile not found") from None
    body = await request.json()
    payload = body.get("payload", "").encode("utf-8")
    result = analyze_profile(profile, payload, settings=request.app.state.settings, repair=False)
    return {"profile_version": profile.version_number, **result}


@router.post("/api/v1/integration-profiles/{profile_id}/publish")
async def publish_profile(
    profile_id: str,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        profile = await integration_service.publish_profile(
            session, client.organization_id, profile_id
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="profile not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return {"published": True, "profile_version": profile.version_number}


@router.get("/api/v1/integration-profiles/{profile_id}/versions")
async def profile_versions(
    profile_id: str,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    return await integration_service.list_profile_versions(
        session, client.organization_id, profile_id
    )
