"""Investigation API (Phase 1).

Operator-authenticated endpoints (called via the Next.js proxy):

- ``GET  /api/v1/investigations/demo-cases``  list bundled synthetic demo cases
- ``POST /api/v1/investigations``             start an investigation
- ``GET  /api/v1/investigations``             list investigations (tenant-scoped)
- ``GET  /api/v1/investigations/{id}``        detail (polls Evolus while running)

Inbound tool endpoint (called by the Evolus workflow, not the browser), guarded by a
dedicated constant-time credential:

- ``POST /api/v1/evolus/tools/validate-case``
"""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from paymentops_api.auth import AuthenticatedClient, get_api_client, get_db
from paymentops_api.db.models import Investigation
from paymentops_api.evolus.demo_cases import list_demo_cases
from paymentops_api.services import investigation_service, repair_service
from paymentops_api.services.case_payload import (
    case_origin,
    load_record,
    synthetic_input_preview,
)

router = APIRouter(tags=["investigations"])

_DISCLAIMER = (
    "Investigation only. Proposed changes are tested on sandbox copies of the synthetic input; "
    "the original payload is never modified. This does not authorize, execute, or settle "
    "payments, and it does not establish account ownership."
)


class StartInvestigationRequest(BaseModel):
    demo_case_key: str = Field(..., description="A server-side synthetic demo case key")
    start_workflow: bool = Field(
        default=True,
        description="Start the Evolus workflow. Set false to prepare deterministically only.",
    )


class UploadInvestigationRequest(BaseModel):
    xml: str = Field(..., description="ISO 20022 XML content (pacs.008.001.08, synthetic only)")
    evidence: dict[str, object] | None = Field(
        default=None, description="Optional supporting-evidence JSON (see docs/PHASE2C_UPLOAD.md)"
    )
    start_workflow: bool = Field(default=True)


class ValidateCaseRequest(BaseModel):
    case_ref: str = Field(..., description="Server-issued case reference")


async def require_tool_credential(
    request: Request,
    x_tool_key: str | None = Header(default=None, alias="X-Tool-Key"),
) -> None:
    """Authenticate the inbound Evolus validation tool with a constant-time comparison."""
    settings = request.app.state.settings
    expected = settings.evolus_tool_api_key
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The PaymentOps validation tool is not configured on this server.",
        )
    if not x_tool_key or not hmac.compare_digest(
        x_tool_key.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid tool credential."
        )


@router.get("/api/v1/investigations/demo-cases")
async def list_demo_cases_endpoint(
    client: AuthenticatedClient = Depends(get_api_client),
) -> list[dict[str, object]]:
    return [
        {
            "key": c.key,
            "name": c.name,
            "message_version": c.message_version,
            "description": c.description,
            "origin": c.origin,
        }
        for c in list_demo_cases()
    ]


@router.post("/api/v1/investigations", status_code=status.HTTP_201_CREATED)
async def start_investigation(
    body: StartInvestigationRequest,
    request: Request,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        inv = await investigation_service.start_investigation(
            session,
            client.organization_id,
            body.demo_case_key,
            settings=request.app.state.settings,
            pipeline=request.app.state.analysis_pipeline,
            registry=request.app.state.iso_registry,
            evolus_client=request.app.state.evolus_client,
            start_workflow=body.start_workflow,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown demo case") from None
    investigation_service.record_start_metric(inv.status)
    return _detail(inv)


@router.get("/api/v1/investigations")
async def list_investigations(
    request: Request,
    limit: int = 50,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    rows = await investigation_service.list_investigations(
        session, client.organization_id, limit=limit
    )
    return [_summary(r) for r in rows]


@router.get("/api/v1/investigations/{investigation_id}")
async def get_investigation(
    investigation_id: str,
    request: Request,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        inv = await investigation_service.get_investigation(
            session, client.organization_id, investigation_id
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="investigation not found") from None
    inv = await investigation_service.refresh_investigation(
        session, inv, client=request.app.state.evolus_client
    )
    return _detail(inv)


@router.post("/api/v1/investigations/upload", status_code=status.HTTP_201_CREATED)
async def upload_investigation(
    body: UploadInvestigationRequest,
    request: Request,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Create an investigation from an uploaded SYNTHETIC pacs.008 payload.

    Content-based upload (the client reads the file and sends its text), consistent with the
    existing ``/analyze`` pattern. Synthetic data only; filenames are never used as storage paths.
    """
    try:
        inv = await investigation_service.start_uploaded_investigation(
            session,
            client.organization_id,
            body.xml.encode("utf-8"),
            body.evidence,
            settings=request.app.state.settings,
            pipeline=request.app.state.analysis_pipeline,
            registry=request.app.state.iso_registry,
            evolus_client=request.app.state.evolus_client,
            start_workflow=body.start_workflow,
        )
    except investigation_service.UploadValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid evidence: {exc}") from None
    investigation_service.record_start_metric(inv.status)
    return _detail(inv)


@router.post("/api/v1/investigations/{investigation_id}/repair/test")
async def test_repair(
    investigation_id: str,
    request: Request,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Validate the agent's proposed repair and test it on a sandbox copy of the payload.

    The original input is never mutated; only allowlisted, evidence-backed changes are applied
    and the sandbox is re-validated by the real deterministic engine.
    """
    try:
        inv = await investigation_service.get_investigation(
            session, client.organization_id, investigation_id
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="investigation not found") from None
    if inv.status != "COMPLETED" or not inv.repair:
        raise HTTPException(
            status_code=409, detail="no completed investigation with a proposal to test"
        )
    inv = await repair_service.test_repair(
        session,
        inv,
        pipeline=request.app.state.analysis_pipeline,
        registry=request.app.state.iso_registry,
    )
    return _detail(inv)


@router.post("/api/v1/evolus/tools/validate-case")
async def validate_case_tool(
    body: ValidateCaseRequest,
    request: Request,
    _: None = Depends(require_tool_credential),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    try:
        return await investigation_service.validate_case_for_tool(
            session,
            request.app.state.settings,
            case_ref=body.case_ref,
            pipeline=request.app.state.analysis_pipeline,
            registry=request.app.state.iso_registry,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="case not found or out of scope") from None
    except PermissionError:
        raise HTTPException(status_code=403, detail="case out of scope") from None


# --------------------------------------------------------------------------- serializers


def _rule_count(inv: Investigation) -> int:
    findings = (inv.deterministic_findings or {}).get("rule_findings")
    return len(findings) if isinstance(findings, list) else 0


def _summary(inv: Investigation) -> dict[str, object]:
    return {
        "investigation_id": inv.investigation_id,
        "demo_case_key": inv.demo_case_key,
        "message_version": inv.message_version,
        "status": inv.status,
        "agent_status": inv.agent_status,
        "validation_status": (inv.deterministic_findings or {}).get("original_validation_status"),
        "rule_count": _rule_count(inv),
        "ruleset_version": inv.ruleset_version,
        "engine_version": inv.engine_version,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
        "updated_at": inv.updated_at.isoformat() if inv.updated_at else None,
        "error": inv.error,
    }


def _detail(inv: Investigation) -> dict[str, object]:
    return {
        **_summary(inv),
        "source": inv.source,
        "input_label": "uploaded" if inv.source == "upload" else "sample",
        "case_origin": case_origin(inv),
        "input_hash": inv.input_hash,
        "evidence_hash": inv.evidence_hash,
        "profile_version": inv.profile_version,
        "evolus_execution_id": inv.evolus_execution_id,
        "evolus_trace_id": inv.evolus_trace_id,
        "deterministic_findings": inv.deterministic_findings,
        "agent_result": inv.agent_result,
        "answer_text": inv.answer_text,
        "supporting_record": inv.supporting_record,
        "evidence_gaps": _evidence_gaps(inv),
        "repair": inv.repair,
        "synthetic_input": synthetic_input_preview(inv),
        "disclaimer": _DISCLAIMER,
    }


def _evidence_gaps(inv: Investigation) -> dict[str, object]:
    """Server-side evidence-gap view.

    Kept separate from the agent's structured list so an empty agent list is never displayed as
    "no evidence missing". Computed at read time from persisted fields, so it is correct for
    historical investigations too without rewriting any stored agent output.
    """
    record = load_record(inv)
    raw_findings = (inv.deterministic_findings or {}).get("rule_findings")
    findings: list[Any] = raw_findings if isinstance(raw_findings, list) else []
    repair = inv.repair if isinstance(inv.repair, dict) else {}
    proposal_obj = repair.get("proposal")
    proposal: dict[str, Any] = proposal_obj if isinstance(proposal_obj, dict) else {}
    sv_obj = proposal.get("server_validation")
    server_validation: dict[str, Any] = sv_obj if isinstance(sv_obj, dict) else {}
    allowed_obj = server_validation.get("allowed")
    allowed: list[Any] = allowed_obj if isinstance(allowed_obj, list) else []
    reported_obj = proposal.get("missing_evidence")
    agent_reported: list[str] = (
        [str(x) for x in reported_obj] if isinstance(reported_obj, list) else []
    )
    # A list with items was clearly supplied; the stored flag (newer records) is authoritative
    # for the empty-array case. Absent + empty => NOT_SUPPLIED ("no structured gaps supplied").
    agent_present = bool(proposal.get("missing_evidence_present")) or bool(agent_reported)
    record_gaps = list(record.gaps) if record is not None else []
    server_derived = repair_service.derive_server_evidence_gaps(findings, record, allowed)
    merged = repair_service.merge_evidence_gaps(
        ("supporting_record", record_gaps),
        ("server_derived", [g["gap"] for g in server_derived]),
        ("agent", agent_reported),
    )
    return {
        "supporting_record": record_gaps,
        "server_derived": server_derived,
        "agent_reported": agent_reported,
        # "PROVIDED" (agent returned the array) vs "NOT_SUPPLIED" (key absent/omitted).
        "agent_reported_status": "PROVIDED" if agent_present else "NOT_SUPPLIED",
        "conflicts": list(record.contradictions) if record is not None else [],
        "merged": merged,
    }
