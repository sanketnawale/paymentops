"""API request/response schemas for payment analysis."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """Request to analyze an inbound payment XML payload."""

    xml: str = Field(..., description="Raw pacs.008 XML payload (untrusted)")
    repair: bool = Field(default=True, description="Generate a repair candidate")
    persist: bool = Field(default=False, description="Persist audit metadata (no raw XML)")
    include_candidate_xml: bool = Field(default=False, description="Return the candidate XML")


class AnalyzeResponse(BaseModel):
    """Structured analysis result. Never contains raw exception details."""

    case_id: str
    message_type: str | None = None
    message_version: str | None = None
    original_validation_status: str
    schema_issues: list[dict[str, Any]] = Field(default_factory=list)
    rule_findings: list[dict[str, Any]] = Field(default_factory=list)
    address_analyses: list[dict[str, Any]] = Field(default_factory=list)
    address_readiness: str | None = None
    repair_status: str | None = None
    candidate_diff: list[dict[str, Any]] = Field(default_factory=list)
    candidate_validation_status: str | None = None
    candidate_xml: str | None = None
    ruleset_version: str | None = None
    address_provider: str | None = None
    address_provider_version: str | None = None
    address_provider_fallback: bool = False
    input_hash: str | None = None
    output_hash: str | None = None
    warnings: list[str] = Field(default_factory=list)
