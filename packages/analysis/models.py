"""Analysis result model (structured, serializable, non-sensitive)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class AnalysisIssue(BaseModel):
    code: str
    severity: str
    path: str | None = None
    message: str


class AnalysisAddress(BaseModel):
    party: str | None = None
    readiness: str | None = None
    evidence_level: str | None = None
    country_code: str | None = None
    town_name: str | None = None
    provider: str | None = None
    provider_version: str | None = None
    note: str | None = None
    fallback: bool = False


class AnalysisDiff(BaseModel):
    path: str
    before: str | None = None
    after: str | None = None
    source: str | None = None
    status: str | None = None


class AnalysisResult(BaseModel):
    case_id: str
    message_type: str | None = None
    message_version: str | None = None
    original_validation_status: str  # valid | invalid
    schema_issues: list[AnalysisIssue] = Field(default_factory=list)
    rule_findings: list[dict[str, Any]] = Field(default_factory=list)
    address_analyses: list[AnalysisAddress] = Field(default_factory=list)
    address_readiness: str | None = None
    repair_status: str | None = None
    candidate_diff: list[AnalysisDiff] = Field(default_factory=list)
    candidate_validation_status: str | None = None
    candidate_xml: str | None = None
    ruleset_version: str | None = None
    address_provider: str | None = None
    address_provider_version: str | None = None
    address_provider_fallback: bool = False
    address_provider_coverage: str | None = None
    input_hash: str | None = None
    output_hash: str | None = None
    warnings: list[str] = Field(default_factory=list)
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IsoAnalysisResult(BaseModel):
    """Result of analyzing ANY supported ISO message (Week 5, registry-based).

    Includes ISO metadata, schema validation, canonical-model version, lifecycle correlation
    (filled by the API service), and the normalized/raw status when the message is a status
    report (pacs.002).
    """

    case_id: str
    message_family: str | None = None
    message_definition: str | None = None
    message_version: str | None = None
    namespace: str | None = None
    message_id: str | None = None
    adapter_version: str | None = None
    schema_validation: bool = False
    schema_version: str | None = None
    original_validation_status: str = "valid"
    schema_issues: list[AnalysisIssue] = Field(default_factory=list)
    rule_findings: list[dict[str, Any]] = Field(default_factory=list)
    address_analyses: list[AnalysisAddress] = Field(default_factory=list)
    address_readiness: str | None = None
    address_provider_coverage: str | None = None
    repair_status: str | None = None
    candidate_diff: list[AnalysisDiff] = Field(default_factory=list)
    candidate_validation_status: str | None = None
    canonical_model_version: str | None = None
    engine_version: str | None = None
    input_hash: str | None = None
    warnings: list[str] = Field(default_factory=list)
    lifecycle_id: str | None = None
    correlation_status: str | None = None
    correlation_evidence: list[str] = Field(default_factory=list)
    correlation_conflicts: list[str] = Field(default_factory=list)
    lifecycle_events: list[dict[str, Any]] = Field(default_factory=list)
    raw_status: str | None = None
    normalized_status: str | None = None
    correlation_profiles: list[dict[str, Any]] = Field(default_factory=list)
    # Week 6 account-reporting fields.
    account_report_type: str | None = None
    account_reports: list[dict[str, Any]] = Field(default_factory=list)
    account_report_ids: list[str] = Field(default_factory=list)
    account_entry_count: int = 0
    account_reconciliation: list[dict[str, Any]] = Field(default_factory=list)
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
