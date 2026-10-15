"""Investigation service (Phase 1).

Orchestrates the deterministic-first investigation flow:

1. Resolve a bundled synthetic demo case (never a client-supplied path/URL).
2. Run the *real* deterministic PaymentOps engine (secure parse -> identify -> XSD validate ->
   canonical map -> rules -> address readiness).
3. Persist an investigation row (metadata + SHA-256 of the input, no raw payload).
4. Start the configured Evolus investigation workflow (once; never retried).
5. Expose a narrowly-scoped validation tool that Evolus calls with a server-issued case_ref.

The engine is authoritative for validation; the agent only interprets.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from paymentops_api.db.models import AuditEvent, Investigation, Organization
from paymentops_api.evolus.client import (
    EvolusClient,
    EvolusError,
    EvolusNotConfiguredError,
    EvolusRateLimitedError,
    WorkflowExecution,
)
from paymentops_api.evolus.demo_cases import DemoCase, get_demo_case
from paymentops_api.logging import get_logger
from paymentops_api.observability import (
    evolus_workflow_runs_total,
    investigations_total,
    tool_validations_total,
)
from paymentops_api.settings import Settings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from analysis.models import IsoAnalysisResult
from analysis.pipeline import AnalysisPipeline
from iso_engine.registry import IsoMessageRegistry
from rules_engine import RULESET_VERSION

logger = get_logger("paymentops.investigation")

_RULE_ID_RE = re.compile(r"\b(?:ISO|SEM|ADR)-\d{3}\b")


# --------------------------------------------------------------------------- deterministic


def payload_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def run_deterministic_validation(
    payload: bytes, *, pipeline: AnalysisPipeline, registry: IsoMessageRegistry
) -> IsoAnalysisResult:
    """Run the real deterministic engine on a synthetic payload (pure, no persistence)."""
    return pipeline.analyze_iso(payload, registry)


def deterministic_record(result: IsoAnalysisResult) -> dict[str, Any]:
    """A serializable record of the deterministic validation output."""
    return {
        "message_family": result.message_family,
        "message_definition": result.message_definition,
        "message_version": result.message_version,
        "namespace": result.namespace,
        "schema_validation": result.schema_validation,
        "original_validation_status": result.original_validation_status,
        "schema_issues": [i.model_dump(mode="json") for i in result.schema_issues],
        "rule_findings": result.rule_findings,
        "address_analyses": [a.model_dump(mode="json") for a in result.address_analyses],
        "address_readiness": result.address_readiness,
        "engine_version": result.engine_version,
        "canonical_model_version": result.canonical_model_version,
        "ruleset_version": RULESET_VERSION,
    }


# --------------------------------------------------------------------------- workflow input


def build_investigation_prompt(demo: DemoCase, case_ref: str) -> str:
    """Build the workflow input text. Contains no secrets and no raw payload."""
    return (
        "Investigate the synthetic PaymentOps demo case.\n"
        f"case_ref: {case_ref}\n"
        f"message_version: {demo.message_version}\n"
        "Required steps:\n"
        "1. Consult the 'PaymentOps Rules' knowledge library for applicable rule identifiers.\n"
        f'2. Call the PaymentOps validation tool with {{"case_ref": "{case_ref}"}} to obtain the '
        "deterministic validation result from the real PaymentOps engine.\n"
        "3. Report evidence-backed findings: cite the rule identifiers and field locations "
        "returned by the tool.\n"
        "4. State which evidence is unavailable and the recommended human next step.\n"
        "Do NOT treat structural validity as proof of payment safety, authorization, settlement, "
        "or account ownership. This is a synthetic demo case; no payment is executed.\n"
    )


# --------------------------------------------------------------------------- tool payload


def build_tool_validation_payload(
    *,
    case_ref: str,
    demo: DemoCase,
    result: IsoAnalysisResult,
    input_sha256: str,
    profile_version: str | None,
    input_unchanged: bool = True,
) -> dict[str, Any]:
    """Structured tool response, clearly separating validation from interpretation."""
    return {
        "tool": "paymentops.validate_case",
        "case_ref": case_ref,
        "synthetic": True,
        "input": {
            "identity_sha256": input_sha256,
            "message_version": result.message_version,
            "demo_case_key": demo.key,
            "demo_case_origin": demo.origin,
            "input_unchanged": input_unchanged,
        },
        "profile": {
            "profile_version": profile_version,
            "ruleset_version": RULESET_VERSION,
            "engine_version": result.engine_version,
            "canonical_model_version": result.canonical_model_version,
        },
        "validation": {
            "status": result.original_validation_status,
            "schema_valid": result.schema_validation,
            "schema_issues": [i.model_dump(mode="json") for i in result.schema_issues],
            "findings": result.rule_findings,
            "address_readiness": result.address_readiness,
        },
        "interpretation_guidance": {
            "authoritative": True,
            "scope": "deterministic validation only",
            "note": (
                "These are deterministic validation results from the PaymentOps engine. They do "
                "not establish payment safety, authorization, settlement, or account ownership, "
                "and must not be presented as such."
            ),
        },
    }


# --------------------------------------------------------------------------- persistence


async def start_investigation(
    session: AsyncSession,
    org: str,
    demo_case_key: str,
    *,
    settings: Settings,
    pipeline: AnalysisPipeline,
    registry: IsoMessageRegistry,
    evolus_client: EvolusClient,
    start_workflow: bool = True,
) -> Investigation:
    """Create an investigation and run the deterministic engine.

    When ``start_workflow`` is True the configured Evolus workflow is started exactly once.
    When False the investigation is prepared deterministically and no workflow is started
    (status ``PREPARED``); this supports smoke tests and tool wiring before the agent's tools
    are attached, without claiming a completed run.
    """
    demo = get_demo_case(demo_case_key)  # KeyError -> caller maps to 404
    payload = demo.load()
    result = run_deterministic_validation(payload, pipeline=pipeline, registry=registry)
    input_sha256 = payload_sha256(payload)

    investigation = Investigation(
        investigation_id=f"inv-{uuid.uuid4().hex[:12]}",
        organization_id=org,
        demo_case_key=demo.key,
        message_version=result.message_version or demo.message_version,
        input_hash=input_sha256,
        ruleset_version=RULESET_VERSION,
        engine_version=result.engine_version,
        profile_version=None,
        status="PENDING",
        deterministic_findings=deterministic_record(result),
        created_at=datetime.now(UTC),
    )
    session.add(investigation)
    await session.commit()
    await session.refresh(investigation)

    if not start_workflow:
        investigation.status = "PREPARED"
        investigation.agent_status = "NOT_STARTED"
        investigation.updated_at = datetime.now(UTC)
        await session.commit()
        return investigation

    await _start_evolus(session, investigation, demo, settings=settings, client=evolus_client)
    return investigation


async def _start_evolus(
    session: AsyncSession,
    inv: Investigation,
    demo: DemoCase,
    *,
    settings: Settings,
    client: EvolusClient,
) -> None:
    if not client.configured:
        inv.status = "FAILED"
        inv.error = (
            "Evolus integration is not configured. Set EVOLUS_ENABLED, EVOLUS_API_KEY, "
            "EVOLUS_APPLICATION_ID and EVOLUS_WORKFLOW_ID, then start a new investigation."
        )
        inv.updated_at = datetime.now(UTC)
        evolus_workflow_runs_total.labels(status="not_configured").inc()
        await session.commit()
        return

    prompt = build_investigation_prompt(demo, inv.investigation_id)
    try:
        run = await client.start_workflow(prompt)
    except EvolusNotConfiguredError as exc:
        inv.status = "FAILED"
        inv.error = str(exc)
    except EvolusRateLimitedError as exc:
        inv.status = "FAILED"
        extra = f" Retry after {exc.retry_after:.0f}s." if exc.retry_after else ""
        inv.error = f"Evolus rate limit reached while starting the investigation.{extra}"
    except EvolusError as exc:
        inv.status = "FAILED"
        inv.error = str(exc)
    else:
        inv.status = "RUNNING"
        inv.evolus_execution_id = run.execution_id
        inv.evolus_trace_id = run.trace_id
        evolus_workflow_runs_total.labels(status="started").inc()
    inv.updated_at = datetime.now(UTC)
    await session.commit()


async def get_investigation(
    session: AsyncSession, org: str, investigation_id: str
) -> Investigation:
    result = await session.execute(
        select(Investigation).where(
            Investigation.investigation_id == investigation_id,
            Investigation.organization_id == org,
        )
    )
    investigation = result.scalar_one_or_none()
    if investigation is None:
        raise LookupError(investigation_id)
    return investigation


async def list_investigations(
    session: AsyncSession, org: str, limit: int = 50
) -> list[Investigation]:
    limit = max(1, min(limit, 200))
    result = await session.execute(
        select(Investigation)
        .where(Investigation.organization_id == org)
        .order_by(Investigation.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def refresh_investigation(
    session: AsyncSession, inv: Investigation, *, client: EvolusClient
) -> Investigation:
    """Poll Evolus for a non-terminal run once (bounded) and update local state."""
    if (
        inv.status not in ("PENDING", "RUNNING")
        or not inv.evolus_execution_id
        or not client.configured
    ):
        return inv

    try:
        execution = await client.get_execution(inv.evolus_execution_id)
    except EvolusRateLimitedError as exc:
        inv.agent_status = "RATE_LIMITED"
        extra = f" Retry after {exc.retry_after:.0f}s." if exc.retry_after else ""
        inv.error = f"Evolus rate limit reached while polling the run.{extra}"
        inv.updated_at = datetime.now(UTC)
        await session.commit()
        return inv
    except EvolusError as exc:
        inv.status = "FAILED"
        inv.agent_status = "POLL_FAILED"
        inv.error = str(exc)
        inv.updated_at = datetime.now(UTC)
        await session.commit()
        return inv

    inv.status = execution.status
    inv.agent_status = execution.raw_status or None
    if execution.trace_id:
        inv.evolus_trace_id = execution.trace_id
    if execution.status == "COMPLETED":
        engine_ids: set[str] | None = None
        raw_findings = (inv.deterministic_findings or {}).get("rule_findings")
        if isinstance(raw_findings, list):
            engine_ids = {
                str(finding["rule_id"])
                for finding in raw_findings
                if isinstance(finding, dict) and finding.get("rule_id")
            }
        inv.agent_result = parse_agent_result(execution, engine_rule_ids=engine_ids)
        inv.error = None
    elif execution.status == "FAILED":
        inv.error = execution.error_text or "The Evolus investigation run reported failure."
    inv.updated_at = datetime.now(UTC)
    await session.commit()
    return inv


# --------------------------------------------------------------------------- agent result


def parse_agent_result(
    execution: WorkflowExecution, *, engine_rule_ids: set[str] | None = None
) -> dict[str, Any]:
    """Parse an agent result defensively. The raw body is always preserved.

    When ``engine_rule_ids`` is provided, the agent's cited rules are constrained to the rules
    the deterministic engine actually reported. This prevents the agent from echoing the whole
    rules catalogue (observed in a real run) being mistaken for case findings.
    """
    parsed: dict[str, Any] = {
        "explanation": None,
        "cited_rules": [],
        "missing_evidence": [],
        "recommended_next_step": None,
        "output_text": execution.output_text,
        "raw": execution.raw,
    }
    structured = execution.result
    if structured:
        parsed["explanation"] = _first_str(
            structured, ("explanation", "summary", "analysis", "answer", "output", "text")
        )
        parsed["cited_rules"] = _extract_rules(structured)
        parsed["missing_evidence"] = _as_str_list(
            structured.get("missing_evidence")
            or structured.get("missingEvidence")
            or structured.get("gaps")
        )
        parsed["recommended_next_step"] = _first_str(
            structured, ("recommended_next_step", "next_step", "nextStep", "recommendation")
        )

    if not parsed["explanation"] and execution.output_text:
        parsed["explanation"] = execution.output_text
    if not parsed["cited_rules"] and execution.output_text:
        text_rules = _rule_ids_from_text(execution.output_text)
        if engine_rule_ids is not None:
            parsed["cited_rules"] = sorted(text_rules & engine_rule_ids)
        else:
            parsed["cited_rules"] = sorted(text_rules)
    return parsed


def _first_str(data: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item)
            elif isinstance(item, dict):
                text = _first_str(item, ("rule_id", "evidence", "detail", "message", "description"))
                if text:
                    out.append(text)
        return out
    return []


def _extract_rules(data: dict[str, Any]) -> list[str]:
    raw = data.get("cited_rules") or data.get("citedRules") or data.get("rules")
    rules = _as_str_list(raw)
    if rules:
        return sorted(set(rules))
    # Fall back to scanning free-text fields for known rule identifiers.
    found: set[str] = set()
    for value in data.values():
        if isinstance(value, str):
            found.update(_rule_ids_from_text(value))
    return sorted(found)


def _rule_ids_from_text(text: str | None) -> set[str]:
    """Rule identifiers mentioned in prose, excluding markdown table rows.

    Observed failure mode: the agent echoes the rules knowledge base as a markdown table
    (``| `ADR-002` | Country missing | ERROR | ... |``), which is not a finding for the case.
    We skip table rows so "cited rules" reflect real findings rather than the rule catalogue,
    while never filtering the report text itself.
    """
    if not text:
        return set()
    found: set[str] = set()
    for line in text.splitlines():
        if "|" in line:
            continue
        found.update(_RULE_ID_RE.findall(line))
    return found


# --------------------------------------------------------------------------- validation tool


async def resolve_investigation_for_tool(
    session: AsyncSession, settings: Settings, case_ref: str
) -> Investigation:
    """Resolve a server-issued case_ref to a demo investigation, enforcing the tenant guard."""
    result = await session.execute(
        select(Investigation).where(Investigation.investigation_id == case_ref)
    )
    inv = result.scalar_one_or_none()
    if inv is None:
        raise LookupError(case_ref)

    if settings.evolus_demo_org_public_id:
        org_result = await session.execute(
            select(Organization).where(Organization.public_id == settings.evolus_demo_org_public_id)
        )
        org = org_result.scalar_one_or_none()
        if org is None or inv.organization_id != org.id:
            raise PermissionError(case_ref)
    return inv


async def validate_case_for_tool(
    session: AsyncSession,
    settings: Settings,
    *,
    case_ref: str,
    pipeline: AnalysisPipeline,
    registry: IsoMessageRegistry,
) -> dict[str, Any]:
    """Validate a synthetic case with the real engine, keyed by a server-issued case_ref."""
    inv = await resolve_investigation_for_tool(session, settings, case_ref)
    demo = get_demo_case(inv.demo_case_key)
    payload = demo.load()
    input_sha256 = payload_sha256(payload)
    input_unchanged = input_sha256 == inv.input_hash
    if not input_unchanged:
        # Bundled fixtures are immutable; a mismatch is surfaced, never hidden.
        logger.warning("investigation_input_hash_mismatch", case_ref=inv.investigation_id)

    result = run_deterministic_validation(payload, pipeline=pipeline, registry=registry)
    payload_out = build_tool_validation_payload(
        case_ref=inv.investigation_id,
        demo=demo,
        result=result,
        input_sha256=input_sha256,
        profile_version=inv.profile_version,
        input_unchanged=input_unchanged,
    )

    tool_validations_total.labels(result=result.original_validation_status).inc()
    session.add(
        AuditEvent(
            organization_id=inv.organization_id,
            case_id=inv.investigation_id,
            event_type="investigation.validation_tool",
            action_metadata={"classification": result.original_validation_status},
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()
    return payload_out


def record_start_metric(status: str) -> None:
    investigations_total.labels(status=status).inc()
