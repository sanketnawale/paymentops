"""Profile-resolved analysis API (authenticated, tenant-scoped)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from integration_profiles.models import IntegrationProfile
from paymentops_api.auth import AuthenticatedClient, get_api_client, get_db
from paymentops_api.db.models import AuditEvent, PaymentCase, RepairCandidate, RuleFinding
from paymentops_api.services import integration_service
from paymentops_api.services.integration_analysis_service import analyze_profile

router = APIRouter(tags=["integrations"])


class AnalyzeRequest(BaseModel):
    payload: str = Field(..., description="Raw input payload (JSON/XML/CSV)")
    repair: bool = True
    include_candidate_xml: bool = False
    idempotency_key: str | None = None


@router.post("/api/v1/integrations/{profile_id}/analyze")
async def profile_analyze(
    profile_id: str,
    body: AnalyzeRequest,
    request: Request,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    if client.allowed_profiles and profile_id not in client.allowed_profiles:
        raise HTTPException(status_code=403, detail="profile not authorized for client")

    try:
        profile = await integration_service.get_profile(session, client.organization_id, profile_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="profile not found") from None
    if profile.status.value != "PUBLISHED":
        raise HTTPException(status_code=409, detail="profile not published")

    if body.idempotency_key:
        existing = await _find_existing_case(session, client.organization_id, body.idempotency_key)
        if existing is not None:
            return _case_to_dict(existing)

    result = analyze_profile(
        profile,
        body.payload.encode("utf-8"),
        settings=request.app.state.settings,
        repair=body.repair,
        include_candidate_xml=body.include_candidate_xml,
    )
    case = await _persist_case(
        session, client.organization_id, profile_id, profile, result, body.idempotency_key
    )
    return {**result, "case_id": case.case_id}


async def _persist_case(
    session: AsyncSession,
    org: str,
    profile_id: str,
    profile: IntegrationProfile,
    result: dict[str, object],
    idem: str | None,
) -> PaymentCase:
    case = PaymentCase(
        case_id=cast(str, result.get("case_id")),
        organization_id=org,
        message_type=profile.input_format.value,
        message_version=cast("str | None", result.get("mapping_version")),
        validation_status=cast("str | None", result.get("original_validation_status")),
        address_readiness=cast("str | None", result.get("address_readiness")),
        repair_status=cast("str | None", result.get("repair_status")),
        ruleset_version=cast("str | None", result.get("ruleset_version")),
        mapping_version=cast("str | None", result.get("mapping_version")),
        integration_profile_version=cast("str | None", result.get("integration_profile_version")),
        engine_version=cast("str | None", result.get("engine_version")),
        address_provider=cast("str | None", result.get("address_provider")),
        address_provider_version=cast("str | None", result.get("address_provider_version")),
        address_provider_coverage=cast("str | None", result.get("address_provider_coverage")),
        input_hash=cast("str | None", result.get("input_hash")),
        output_hash=cast("str | None", result.get("output_hash")),
        status=(
            "REVIEW_REQUIRED"
            if result.get("candidate_validation_status") == "REVIEW_REQUIRED"
            else "ANALYZED"
        ),
        idempotency_key=idem,
        created_at=datetime.now(UTC),
    )
    session.add(case)
    for finding in cast(list[dict[str, object]], result.get("rule_findings") or []):
        session.add(
            RuleFinding(
                organization_id=org,
                case_id=case.case_id,
                rule_id=str(finding.get("rule_id", "unknown")),
                severity=str(finding.get("severity", "unknown")),
                target=str(finding.get("target", ""))[:256],
                message=str(finding.get("message", ""))[:256],
            )
        )
    if result.get("candidate_validation_status"):
        session.add(
            RepairCandidate(
                organization_id=org,
                case_id=case.case_id,
                candidate_id=f"RC-{case.case_id}",
                status=str(result.get("candidate_validation_status")),
                xml_sha256=cast("str | None", result.get("output_hash")),
            )
        )
    session.add(AuditEvent(case_id=case.case_id, event_type="analysis_completed"))
    await session.commit()
    await session.refresh(case)
    return case


async def _find_existing_case(session: AsyncSession, org: str, idem: str) -> PaymentCase | None:
    result = await session.execute(
        select(PaymentCase).where(
            PaymentCase.organization_id == org, PaymentCase.idempotency_key == idem
        )
    )
    return result.scalar_one_or_none()


def _case_to_dict(case: PaymentCase) -> dict[str, object]:
    return {
        "case_id": case.case_id,
        "status": case.status,
        "mapping_version": case.mapping_version,
        "integration_profile_version": case.integration_profile_version,
        "address_provider_coverage": case.address_provider_coverage,
        "idempotent": True,
    }
