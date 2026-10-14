"""Matching / reconciliation API (tenant-scoped).

Non-transactional: a CONFIRMED match is a PaymentOps reconciliation decision only. It never
executes or settles a payment.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from matching_engine import (
    MatchDecision,
    MatchingPolicy,
    MatchRecord,
    default_policy,
)
from paymentops_api.auth import (
    AuthenticatedClient,
    get_actor_identity,
    get_api_client,
    get_db,
)
from paymentops_api.db.models import MatchCandidate, MatchRecordRow, MatchRun
from paymentops_api.queue import enqueue_reconciliation
from paymentops_api.services import matching_service

router = APIRouter(tags=["matching"])


class CreatePolicyRequest(BaseModel):
    name: str


class PolicyRequest(BaseModel):
    policy: MatchingPolicy


class RecordRequest(BaseModel):
    record: MatchRecord


class EvaluateRequest(BaseModel):
    record_a_id: str | None = None
    record_b_id: str | None = None
    record_a: MatchRecord | None = None
    record_b: MatchRecord | None = None
    policy_id: str | None = None


class CandidateSearchRequest(BaseModel):
    source: MatchRecord
    policy_id: str | None = None
    max_candidates: int = Field(default=20, ge=1, le=100)


class ReconciliationRequest(BaseModel):
    source_records: list[MatchRecord]
    candidate_records: list[MatchRecord]
    policy_id: str | None = None


class DecideRequest(BaseModel):
    action: str
    operator: str | None = None
    note: str | None = None


@router.post("/api/v1/matching/policies", status_code=201)
async def create_policy(
    body: CreatePolicyRequest,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    row = await matching_service.create_policy(session, client.organization_id, body.name)
    return {"policy_id": str(row.id), "status": row.status}


@router.post("/api/v1/matching/policies/{policy_id}/publish")
async def publish_policy(
    policy_id: str,
    body: PolicyRequest,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        version = await matching_service.publish_policy(
            session, client.organization_id, policy_id, body.policy
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="matching policy not found") from None
    return {"policy_id": policy_id, "version": version.version_number}


@router.get("/api/v1/matching/policies")
async def list_policies(
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    rows = await matching_service.list_policies(session, client.organization_id)
    return [{"policy_id": str(r.id), "name": r.name, "status": r.status} for r in rows]


@router.post("/api/v1/matching/records", status_code=201)
async def create_record(
    body: RecordRequest,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    row = await matching_service.create_match_record(session, client.organization_id, body.record)
    return {"record_id": row.record_id, "id": str(row.id)}


@router.get("/api/v1/matching/records")
async def list_records(
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    rows = await matching_service.list_match_records(session, client.organization_id)
    return [_record_dict(r) for r in rows]


@router.get("/api/v1/matching/records/{record_id}")
async def get_record(
    record_id: str,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        row = await matching_service.get_match_record(session, client.organization_id, record_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="match record not found") from None
    return _record_dict(row)


@router.post("/api/v1/matching/evaluate")
async def evaluate(
    body: EvaluateRequest,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    policy = await _policy(session, client.organization_id, body.policy_id)
    record_a, record_b = await _resolve_pair(session, client.organization_id, body)
    decision = await matching_service.evaluate_records(
        session, client.organization_id, record_a, record_b, policy
    )
    return _decision_dict(decision)


@router.post("/api/v1/matching/candidates")
async def candidates(
    body: CandidateSearchRequest,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    policy = await _policy(session, client.organization_id, body.policy_id)
    ranked = await matching_service.search_candidates(
        session, client.organization_id, body.source, policy, max_candidates=body.max_candidates
    )
    return [c.model_dump() for c in ranked]


@router.post("/api/v1/matching/reconciliations", status_code=202)
async def start_reconciliation(
    body: ReconciliationRequest,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    if not body.source_records and not body.candidate_records:
        raise HTTPException(status_code=422, detail="no records provided")
    source_ids = [r.record_id for r in body.source_records]
    cand_ids = [r.record_id for r in body.candidate_records]
    for r in body.source_records + body.candidate_records:
        await matching_service.create_match_record(session, client.organization_id, r)
    run = await matching_service.create_reconciliation_run(
        session,
        client.organization_id,
        source_dataset={"record_ids": source_ids},
        candidate_dataset={"record_ids": cand_ids},
        policy_id=body.policy_id,
    )
    enqueue_reconciliation(str(run.id))
    return {"run_id": str(run.id), "status": run.status}


@router.get("/api/v1/matching/reconciliations")
async def list_reconciliations(
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    runs = await matching_service.list_runs(session, client.organization_id)
    return [_run_dict(r) for r in runs]


@router.get("/api/v1/matching/reconciliations/{run_id}")
async def get_reconciliation(
    run_id: str,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        run = await matching_service.get_run(session, client.organization_id, run_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="reconciliation run not found") from None
    candidates = await matching_service.list_run_candidates(session, client.organization_id, run_id)
    data = _run_dict(run)
    data["candidates"] = [_candidate_dict(c) for c in candidates]
    return data


@router.get("/api/v1/matching/reconciliations/{run_id}/report")
async def reconciliation_report(
    run_id: str,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await matching_service.get_run(session, client.organization_id, run_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="reconciliation run not found") from None
    candidates = await matching_service.list_run_candidates(session, client.organization_id, run_id)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "source_reference",
            "candidate_reference",
            "classification",
            "match_score",
            "critical_conflict",
            "review_required",
        ]
    )
    for c in candidates:
        conflict = ",".join(str(x.get("field", "")) for x in c.critical_conflicts)
        writer.writerow(
            [
                _safe_csv(c.source_record_id),
                _safe_csv(c.candidate_record_id),
                _safe_csv(c.classification),
                c.match_score,
                _safe_csv(conflict),
                _safe_csv(c.status),
            ]
        )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="reconciliation-{run_id}.csv"'},
    )


@router.post("/api/v1/matching/candidates/{candidate_id}/decide")
async def decide_candidate(
    candidate_id: str,
    body: DecideRequest,
    client: AuthenticatedClient = Depends(get_api_client),
    actor: str | None = Depends(get_actor_identity),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        cand = await matching_service.decide_candidate(
            session,
            client.organization_id,
            candidate_id,
            body.action,
            operator=actor or body.operator,
            note=body.note,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="match candidate not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return {"candidate_id": str(cand.id), "status": cand.status, "action": body.action}


# ---------------------------------------------------------------- helpers


async def _policy(session: AsyncSession, org: str, policy_id: str | None) -> MatchingPolicy:
    if policy_id:
        try:
            return await matching_service.get_published_policy(session, org, policy_id)
        except LookupError:
            raise HTTPException(status_code=404, detail="matching policy not found") from None
    return default_policy(org)


async def _resolve_pair(
    session: AsyncSession, org: str, body: EvaluateRequest
) -> tuple[MatchRecord, MatchRecord]:
    if body.record_a_id and body.record_b_id:
        a = await _get_record_domain(session, org, body.record_a_id)
        b = await _get_record_domain(session, org, body.record_b_id)
        return a, b
    if body.record_a and body.record_b:
        return body.record_a, body.record_b
    raise HTTPException(
        status_code=422, detail="provide record_a_id/record_b_id or record_a/record_b"
    )


async def _get_record_domain(session: AsyncSession, org: str, record_id: str) -> MatchRecord:
    try:
        row = await matching_service.get_match_record(session, org, record_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="match record not found") from None
    return matching_service._row_to_domain(row)


def _record_dict(row: MatchRecordRow) -> dict[str, object]:
    return matching_service._row_to_domain(row).model_dump(mode="json")


def _decision_dict(decision: MatchDecision) -> dict[str, object]:
    return {
        "record_a_id": decision.record_a_id,
        "record_b_id": decision.record_b_id,
        "classification": decision.classification.value,
        "match_score": decision.match_score,
        "critical_conflicts": [c.model_dump() for c in decision.critical_conflicts],
        "field_results": [f.model_dump(mode="json") for f in decision.field_results],
        "explanation_codes": decision.explanation_codes,
        "policy_version": decision.policy_version,
        "engine_version": decision.engine_version,
    }


def _run_dict(run: MatchRun) -> dict[str, object]:
    return {
        "run_id": str(run.id),
        "run_type": run.run_type,
        "status": run.status,
        "policy_version": run.policy_version,
        "total": run.total,
        "matched": run.matched,
        "possible_match": run.possible_match,
        "review_required": run.review_required,
        "unmatched": run.unmatched,
        "duplicate_candidate": run.duplicate_candidate,
        "failed": run.failed,
        "report": run.report,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


def _candidate_dict(c: MatchCandidate) -> dict[str, object]:
    return {
        "candidate_id": str(c.id),
        "source_record_id": c.source_record_id,
        "candidate_record_id": c.candidate_record_id,
        "match_score": c.match_score,
        "classification": c.classification,
        "critical_conflicts": c.critical_conflicts,
        "status": c.status,
        "operator": c.operator,
        "note": c.note,
    }


def _safe_csv(value: Any) -> str:
    """Protect against CSV formula injection (Task 35)."""
    s = str(value) if value is not None else ""
    if s.startswith(("=", "+", "-", "@")):
        return "'" + s
    return s
