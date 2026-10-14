"""Matching service: policy management, match records, candidate retrieval, reconciliation,
and operator decisions. All operations are tenant-scoped by ``organization_id``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from paymentops_api.db.models import (
    MatchCandidate,
    MatchingPolicyRow,
    MatchingPolicyVersion,
    MatchRecordRow,
    MatchRun,
)
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from matching_engine import (
    CandidateMatch,
    FieldMatchResult,
    MatchClassification,
    MatchDecision,
    MatchingPolicy,
    MatchRecord,
    default_policy,
    evaluate_pair,
    narrowing_criteria,
)
from matching_engine.candidates import DEFAULT_MAX_CANDIDATES
from matching_engine.normalization import normalize_reference

ENGINE_VERSION = "0.2.0"


# ---------------------------------------------------------------- policies


async def create_policy(session: AsyncSession, org: str, name: str) -> MatchingPolicyRow:
    row = MatchingPolicyRow(organization_id=org, name=name, status="DRAFT")
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def list_policies(session: AsyncSession, org: str) -> list[MatchingPolicyRow]:
    result = await session.execute(
        select(MatchingPolicyRow)
        .where(MatchingPolicyRow.organization_id == org)
        .order_by(MatchingPolicyRow.created_at.desc())
    )
    return list(result.scalars().all())


async def get_policy_row(session: AsyncSession, org: str, policy_id: str) -> MatchingPolicyRow:
    result = await session.execute(
        select(MatchingPolicyRow).where(
            MatchingPolicyRow.id == policy_id, MatchingPolicyRow.organization_id == org
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise LookupError("matching policy not found")
    return row


async def publish_policy(
    session: AsyncSession, org: str, policy_id: str, policy: MatchingPolicy
) -> MatchingPolicyVersion:
    """Publish a policy as an immutable version. The published version is what matchers use."""
    row = await get_policy_row(session, org, policy_id)
    version = await _next_version(session, org, policy_id)
    policy = policy.model_copy(update={"id": policy_id, "organization_id": org, "version": version})
    pv = MatchingPolicyVersion(
        policy_id=row.id,
        organization_id=org,
        version_number=version,
        name=policy.name,
        field_weights=policy.field_weights,
        thresholds=policy.thresholds,
        date_tolerances=policy.date_tolerances,
        amount_tolerances=policy.amount_tolerances,
        critical_fields=policy.critical_fields,
        fuzzy_algorithms=policy.fuzzy_algorithms,
        published_at=datetime.now(UTC),
    )
    session.add(pv)
    row.status = "PUBLISHED"
    row.published_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(pv)
    return pv


async def _next_version(session: AsyncSession, org: str, policy_id: str) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(MatchingPolicyVersion)
        .where(
            MatchingPolicyVersion.policy_id == policy_id,
            MatchingPolicyVersion.organization_id == org,
        )
    )
    return int(result.scalar_one() or 0) + 1


async def get_published_policy(
    session: AsyncSession, org: str, policy_id: str | None
) -> MatchingPolicy:
    """Resolve the latest published version of a policy into a MatchingPolicy domain model."""
    if policy_id is None:
        return default_policy(org, name="Development Baseline")
    pv_result = await session.execute(
        select(MatchingPolicyVersion)
        .where(
            MatchingPolicyVersion.policy_id == policy_id,
            MatchingPolicyVersion.organization_id == org,
        )
        .order_by(MatchingPolicyVersion.version_number.desc())
    )
    pv = pv_result.scalars().first()
    if pv is None:
        # No published version -> fall back to development baseline (documented).
        return default_policy(org, name="Development Baseline")
    return MatchingPolicy(
        id=str(pv.policy_id),
        organization_id=org,
        name=pv.name,
        version=pv.version_number,
        status="PUBLISHED",
        field_weights=cast(dict[str, float], pv.field_weights),
        thresholds=cast(dict[str, float], pv.thresholds),
        date_tolerances=cast(dict[str, int], pv.date_tolerances),
        amount_tolerances=cast(dict[str, float], pv.amount_tolerances),
        critical_fields=pv.critical_fields,
        fuzzy_algorithms=cast(dict[str, str], pv.fuzzy_algorithms),
        published_at=pv.published_at,
    )


# ---------------------------------------------------------------- match records


async def create_match_record(
    session: AsyncSession, org: str, record: MatchRecord
) -> MatchRecordRow:
    row = _domain_to_row(org, record)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def get_match_record(session: AsyncSession, org: str, record_id: str) -> MatchRecordRow:
    result = await session.execute(
        select(MatchRecordRow).where(
            MatchRecordRow.record_id == record_id, MatchRecordRow.organization_id == org
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise LookupError("match record not found")
    return row


async def list_match_records(
    session: AsyncSession, org: str, *, limit: int = 100
) -> list[MatchRecordRow]:
    result = await session.execute(
        select(MatchRecordRow)
        .where(MatchRecordRow.organization_id == org)
        .order_by(MatchRecordRow.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


def _domain_to_row(org: str, record: MatchRecord) -> MatchRecordRow:
    return MatchRecordRow(
        organization_id=org,
        record_id=record.record_id,
        record_type=record.record_type.value,
        profile_id=record.profile_id,
        source_system=record.source_system,
        message_type=record.message_type,
        instruction_id=record.instruction_id,
        end_to_end_id=record.end_to_end_id,
        transaction_id=record.transaction_id,
        amount=record.amount,
        currency=record.currency,
        booking_date=record.booking_date,
        value_date=record.value_date,
        debtor_name=record.debtor_name,
        creditor_name=record.creditor_name,
        debtor_account=record.debtor_account,
        creditor_account=record.creditor_account,
        debtor_agent=record.debtor_agent,
        creditor_agent=record.creditor_agent,
        remittance_reference=record.remittance_reference,
        external_reference=record.external_reference,
        country=record.country,
        source_hash=record.source_hash,
        metadata_json=record.metadata,
    )


def _row_to_domain(row: MatchRecordRow) -> MatchRecord:
    from matching_engine.models import RecordType

    return MatchRecord(
        record_id=row.record_id,
        record_type=RecordType(row.record_type),
        organization_id=str(row.organization_id),
        profile_id=row.profile_id,
        source_system=row.source_system,
        message_type=row.message_type,
        instruction_id=row.instruction_id,
        end_to_end_id=row.end_to_end_id,
        transaction_id=row.transaction_id,
        amount=row.amount,
        currency=row.currency,
        booking_date=row.booking_date,
        value_date=row.value_date,
        debtor_name=row.debtor_name,
        creditor_name=row.creditor_name,
        debtor_account=row.debtor_account,
        creditor_account=row.creditor_account,
        debtor_agent=row.debtor_agent,
        creditor_agent=row.creditor_agent,
        remittance_reference=row.remittance_reference,
        external_reference=row.external_reference,
        country=row.country,
        source_hash=row.source_hash,
        metadata_json=row.metadata,
    )


# ---------------------------------------------------------------- candidate retrieval


async def candidate_records(
    session: AsyncSession,
    org: str,
    source: MatchRecordRow,
    policy: MatchingPolicy,
    *,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    exclude_id: str | None = None,
    candidate_types: list[str] | None = None,
) -> list[MatchRecordRow]:
    """Retrieve bounded, tenant-scoped candidate records via narrowing criteria."""
    domain = _row_to_domain(source)
    crit = narrowing_criteria(domain, policy, max_candidates=max_candidates)

    stmt: Select[Any] = select(MatchRecordRow).where(
        MatchRecordRow.organization_id == org,
    )
    if candidate_types:
        stmt = stmt.where(MatchRecordRow.record_type.in_(candidate_types))
    elif not source.record_type:
        pass
    if exclude_id:
        stmt = stmt.where(MatchRecordRow.record_id != exclude_id)
    if crit.get("currency"):
        stmt = stmt.where(MatchRecordRow.currency == crit["currency"])
    if "amount_min" in crit and "amount_max" in crit:
        stmt = stmt.where(
            MatchRecordRow.amount >= crit["amount_min"], MatchRecordRow.amount <= crit["amount_max"]
        )
    if crit.get("date_fields"):
        # At least one date field within the window.
        window = crit["date_window_days"]
        date_conds = []
        for field, dval in crit["date_fields"]:
            col = (
                MatchRecordRow.booking_date
                if field == "booking_date"
                else MatchRecordRow.value_date
            )
            start = dval - timedelta(days=window)
            end = dval + timedelta(days=window)
            date_conds.append(col.between(start, end))
        if date_conds:
            stmt = stmt.where(or_(*date_conds))
    # Reference/account narrowing is done in-memory (normalization-aware), not in SQL,
    # because references/accounts may differ in formatting (hyphens/spaces/case).
    stmt = stmt.limit(max_candidates)
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------- evaluation


async def evaluate_records(
    session: AsyncSession,
    org: str,
    record_a: MatchRecord,
    record_b: MatchRecord,
    policy: MatchingPolicy,
) -> MatchDecision:
    if record_a.organization_id != org or record_b.organization_id != org:
        raise PermissionError("cross-tenant match evaluation denied")
    return evaluate_pair(record_a, record_b, policy, engine_version=ENGINE_VERSION)


async def search_candidates(
    session: AsyncSession,
    org: str,
    source: MatchRecord,
    policy: MatchingPolicy,
    *,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> list[CandidateMatch]:
    source_row = await _ensure_record(session, org, source)
    rows = await candidate_records(
        session, org, source_row, policy, max_candidates=max_candidates, exclude_id=source.record_id
    )
    # Apply normalization-aware reference/account narrowing in-memory.
    narrowed = _filter_candidates(source, [_row_to_domain(r) for r in rows], policy, max_candidates)
    ranked: list[CandidateMatch] = []
    for cand in narrowed:
        decision = evaluate_pair(source, cand, policy, engine_version=ENGINE_VERSION)
        if decision.match_score <= 0:
            continue
        ranked.append(
            CandidateMatch(
                candidate_id=cand.record_id,
                match_score=decision.match_score,
                classification=decision.classification,
                top_evidence=_top_evidence(decision),
                critical_conflicts=decision.critical_conflicts,
            )
        )
    ranked.sort(key=lambda c: c.match_score, reverse=True)
    return ranked[:max_candidates]


async def _ensure_record(session: AsyncSession, org: str, record: MatchRecord) -> MatchRecordRow:
    existing = await session.execute(
        select(MatchRecordRow).where(
            MatchRecordRow.record_id == record.record_id, MatchRecordRow.organization_id == org
        )
    )
    row = existing.scalar_one_or_none()
    if row is not None:
        return row
    return await create_match_record(session, org, record)


def _top_evidence(decision: MatchDecision, limit: int = 6) -> list[FieldMatchResult]:
    scored = [
        fr
        for fr in decision.field_results
        if fr.status.value in ("EXACT", "MISMATCH")
        and (fr.similarity >= 85 or fr.status.value == "MISMATCH")
    ]
    scored.sort(key=lambda fr: (fr.similarity, fr.weight), reverse=True)
    return scored[:limit]


# ---------------------------------------------------------------- reconciliation runs


async def create_reconciliation_run(
    session: AsyncSession,
    org: str,
    *,
    source_dataset: dict[str, Any],
    candidate_dataset: dict[str, Any],
    policy_id: str | None,
) -> MatchRun:
    policy = (
        await get_published_policy(session, org, policy_id) if policy_id else default_policy(org)
    )
    row = MatchRun(
        organization_id=org,
        run_type="RECONCILIATION",
        status="QUEUED",
        policy_id=policy_id,
        policy_version=str(policy.version),
        source_dataset=source_dataset,
        candidate_dataset=candidate_dataset,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def execute_reconciliation(
    session: AsyncSession,
    org: str,
    run_id: str,
    *,
    source_records: list[MatchRecord],
    candidate_records: list[MatchRecord],
    policy: MatchingPolicy,
) -> MatchRun:
    run = await _get_run(session, org, run_id)
    run.status = "RUNNING"
    run.started_at = datetime.now(UTC)
    await session.commit()

    counts = {
        "total": len(source_records),
        "matched": 0,
        "possible_match": 0,
        "review_required": 0,
        "unmatched": 0,
        "duplicate_candidate": 0,
        "failed": 0,
    }
    # One-to-one safety: track which candidate records are already claimed.
    claimed: dict[str, str] = {}
    matched_candidates: list[tuple[MatchRecord, MatchRecord, MatchDecision]] = []

    for src in source_records:
        try:
            candidates = _filter_candidates(src, candidate_records, policy, DEFAULT_MAX_CANDIDATES)
            if not candidates:
                counts["unmatched"] += 1
                continue
            decisions = [
                (cand, evaluate_pair(src, cand, policy, engine_version=ENGINE_VERSION))
                for cand in candidates
            ]
            # strongest first
            decisions.sort(key=lambda x: x[1].match_score, reverse=True)
            best = decisions[0]
            strong = [d for d in decisions if d[1].classification == MatchClassification.MATCHED]

            if best[1].classification == MatchClassification.UNMATCHED:
                counts["unmatched"] += 1
                continue

            # many-to-one / one-to-many ambiguity
            if len(strong) > 1:
                classification = MatchClassification.DUPLICATE_CANDIDATE
                counts["duplicate_candidate"] += 1
            elif best[0].record_id in claimed and claimed[best[0].record_id] != src.record_id:
                classification = MatchClassification.REVIEW_REQUIRED
                counts["review_required"] += 1
            else:
                classification = best[1].classification
                if classification == MatchClassification.MATCHED:
                    counts["matched"] += 1
                elif classification == MatchClassification.POSSIBLE_MATCH:
                    counts["possible_match"] += 1
                else:
                    counts["review_required"] += 1

            if classification in (MatchClassification.MATCHED, MatchClassification.POSSIBLE_MATCH):
                claimed[best[0].record_id] = src.record_id
            matched_candidates.append((src, best[0], best[1]))

            await _persist_candidate(
                session,
                org,
                run.id,
                src,
                best[0],
                best[1],
                classification,
            )
        except Exception:  # noqa: BLE001 - per-source isolation
            counts["failed"] += 1

    run.total = counts["total"]
    run.matched = counts["matched"]
    run.possible_match = counts["possible_match"]
    run.review_required = counts["review_required"]
    run.unmatched = counts["unmatched"]
    run.duplicate_candidate = counts["duplicate_candidate"]
    run.failed = counts["failed"]
    run.report = cast("dict[str, object]", counts)
    run.status = "COMPLETED" if counts["failed"] == 0 else "PARTIAL"
    run.completed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(run)
    return run


def _filter_candidates(
    source: MatchRecord, candidates: list[MatchRecord], policy: MatchingPolicy, max_candidates: int
) -> list[MatchRecord]:
    """Narrow a bounded candidate set in-memory using narrowing criteria."""
    crit = narrowing_criteria(source, policy, max_candidates=max_candidates)
    results: list[MatchRecord] = []
    for cand in candidates:
        if cand.record_id == source.record_id:
            continue
        if _candidate_matches(cand, crit):
            results.append(cand)
    return results[:max_candidates]


def _candidate_matches(cand: MatchRecord, crit: dict[str, Any]) -> bool:
    if crit.get("currency") and cand.currency and cand.currency != crit["currency"]:
        return False
    if "amount_min" in crit and "amount_max" in crit and cand.amount is not None:
        if not (crit["amount_min"] <= cand.amount <= crit["amount_max"]):
            return False
    if crit.get("date_fields") and cand.value_date is None and cand.booking_date is None:
        pass
    elif crit.get("date_fields"):
        window = crit["date_window_days"]
        within = False
        for field, dval in crit["date_fields"]:
            cd = cand.booking_date if field == "booking_date" else cand.value_date
            if cd is not None and abs((cd - dval).days) <= window:
                within = True
                break
        if not within:
            return False
    if crit.get("reference_prefix"):
        prefix = str(crit["reference_prefix"])
        ref = cand.remittance_reference or cand.external_reference or ""
        norm = normalize_reference(ref)
        if norm is None or norm[:8] != prefix:
            return False
    if crit.get("account"):
        acc = str(crit["account"]).replace(" ", "").replace("-", "").upper()
        acct = cand.debtor_account or cand.creditor_account or ""
        if acct.replace(" ", "").replace("-", "").upper() != acc:
            return False
    return True


async def _persist_candidate(
    session: AsyncSession,
    org: str,
    run_id: uuid.UUID,
    src: MatchRecord,
    cand: MatchRecord,
    decision: MatchDecision,
    classification: MatchClassification,
) -> None:
    session.add(
        MatchCandidate(
            organization_id=org,
            run_id=run_id,
            source_record_id=src.record_id,
            candidate_record_id=cand.record_id,
            match_score=decision.match_score,
            classification=classification.value,
            critical_conflicts=[c.model_dump() for c in decision.critical_conflicts],
            field_results=[f.model_dump() for f in decision.field_results],
            explanation_codes=decision.explanation_codes,
            policy_version=decision.policy_version,
            engine_version=decision.engine_version,
            status="PENDING",
        )
    )


async def _get_run(session: AsyncSession, org: str, run_id: str) -> MatchRun:
    result = await session.execute(
        select(MatchRun).where(MatchRun.id == run_id, MatchRun.organization_id == org)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise LookupError("reconciliation run not found")
    return run


async def get_run(session: AsyncSession, org: str, run_id: str) -> MatchRun:
    return await _get_run(session, org, run_id)


async def list_runs(session: AsyncSession, org: str) -> list[MatchRun]:
    result = await session.execute(
        select(MatchRun).where(MatchRun.organization_id == org).order_by(MatchRun.created_at.desc())
    )
    return list(result.scalars().all())


async def list_run_candidates(session: AsyncSession, org: str, run_id: str) -> list[MatchCandidate]:
    result = await session.execute(
        select(MatchCandidate).where(
            MatchCandidate.run_id == run_id, MatchCandidate.organization_id == org
        )
    )
    return list(result.scalars().all())


async def decide_candidate(
    session: AsyncSession,
    org: str,
    candidate_id: str,
    action: str,
    *,
    operator: str | None,
    note: str | None,
) -> MatchCandidate:
    result = await session.execute(
        select(MatchCandidate).where(
            MatchCandidate.id == candidate_id, MatchCandidate.organization_id == org
        )
    )
    cand = result.scalar_one_or_none()
    if cand is None:
        raise LookupError("match candidate not found")
    if action not in ("confirm", "reject", "duplicate", "review"):
        raise ValueError(f"unsupported action '{action}'")
    status_map = {
        "confirm": "CONFIRMED",
        "reject": "REJECTED",
        "duplicate": "DUPLICATE",
        "review": "REVIEW_REQUIRED",
    }
    cand.status = status_map[action]
    cand.operator = operator
    cand.note = note
    cand.decided_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(cand)
    return cand
