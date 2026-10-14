"""Analysis service: runs the pipeline, persists audit metadata, emits metrics.

This is the application service boundary. It owns persistence and observability concerns and
keeps the pipeline (packages/analysis) pure. Raw XML is never persisted.
"""

from __future__ import annotations

import time

from paymentops_api.db.models import (
    AnalysisRun,
    AuditEvent,
    PaymentCase,
    RepairCandidate,
    RuleFinding,
)
from paymentops_api.observability import (
    address_resolution_total,
    analysis_duration,
    analysis_total,
    repair_candidates_total,
    rule_findings_total,
    validation_failures_total,
)
from paymentops_api.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from sqlalchemy.ext.asyncio import AsyncSession

from analysis.models import AnalysisResult
from analysis.pipeline import AnalysisPipeline


class AnalysisService:
    def __init__(self, pipeline: AnalysisPipeline) -> None:
        self._pipeline = pipeline

    async def analyze(
        self,
        request: AnalyzeRequest,
        *,
        session: AsyncSession | None = None,
        organization_id: str | None = None,
    ) -> AnalyzeResponse:
        start = time.perf_counter()
        payload = request.xml.encode("utf-8")

        result = self._pipeline.analyze(
            payload,
            repair=request.repair,
            include_candidate_xml=request.include_candidate_xml,
        )
        duration_s = time.perf_counter() - start

        # --- Metrics (low cardinality) ---
        message_type = result.message_type or "unknown"
        status = "ok" if result.original_validation_status == "valid" else "invalid"
        analysis_total.labels(status=status, message_type=message_type).inc()
        analysis_duration.labels(message_type=message_type).observe(duration_s)
        if result.original_validation_status == "invalid":
            validation_failures_total.labels(message_type=message_type).inc()
        for finding in result.rule_findings:
            rule_findings_total.labels(
                rule_category=finding.get("rule_id", "unknown").split("-")[0],
                severity=finding.get("severity", "unknown"),
            ).inc()
        for addr in result.address_analyses:
            address_resolution_total.labels(readiness=addr.readiness or "unknown").inc()
        repair_candidates_total.labels(status=result.repair_status or "none").inc()

        # --- Persistence (metadata + hashes only; never raw XML) ---
        if request.persist and session is not None:
            await self._persist(
                session, result, duration_ms=int(duration_s * 1000), organization_id=organization_id
            )

        return self._to_response(result)

    async def _persist(
        self,
        session: AsyncSession,
        result: AnalysisResult,
        *,
        duration_ms: int,
        organization_id: str | None = None,
    ) -> None:
        case = PaymentCase(
            case_id=result.case_id,
            organization_id=organization_id,
            message_type=result.message_type,
            message_version=result.message_version,
            validation_status=result.original_validation_status,
            address_readiness=result.address_readiness,
            repair_status=result.repair_status,
            ruleset_version=result.ruleset_version,
            address_provider=result.address_provider,
            address_provider_version=result.address_provider_version,
            address_provider_coverage=result.address_provider_coverage,
            input_hash=result.input_hash,
            output_hash=result.output_hash,
        )
        session.add(case)
        session.add(
            AnalysisRun(case_id=result.case_id, status="completed", duration_ms=duration_ms)
        )
        for finding in result.rule_findings:
            session.add(
                RuleFinding(
                    case_id=result.case_id,
                    rule_id=str(finding.get("rule_id", "unknown")),
                    severity=str(finding.get("severity", "unknown")),
                    target=str(finding.get("target", ""))[:256],
                    message=str(finding.get("message", ""))[:256],
                )
            )
        if result.candidate_validation_status:
            session.add(
                RepairCandidate(
                    case_id=result.case_id,
                    candidate_id=f"RC-{result.case_id}",
                    status=result.candidate_validation_status,
                    xml_sha256=result.output_hash,
                )
            )
        session.add(AuditEvent(case_id=result.case_id, event_type="analysis_completed"))
        await session.commit()

    def _to_response(self, result: AnalysisResult) -> AnalyzeResponse:
        return AnalyzeResponse(
            case_id=result.case_id,
            message_type=result.message_type,
            message_version=result.message_version,
            original_validation_status=result.original_validation_status,
            schema_issues=[i.model_dump() for i in result.schema_issues],
            rule_findings=result.rule_findings,
            address_analyses=[a.model_dump() for a in result.address_analyses],
            address_readiness=result.address_readiness,
            repair_status=result.repair_status,
            candidate_diff=[d.model_dump() for d in result.candidate_diff],
            candidate_validation_status=result.candidate_validation_status,
            candidate_xml=result.candidate_xml,
            ruleset_version=result.ruleset_version,
            address_provider=result.address_provider,
            address_provider_version=result.address_provider_version,
            address_provider_fallback=result.address_provider_fallback,
            input_hash=result.input_hash,
            output_hash=result.output_hash,
            warnings=result.warnings,
        )
