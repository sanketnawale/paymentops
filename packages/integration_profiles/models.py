"""Integration Profile domain model.

A profile defines how a customer's input is mapped to the canonical model and which
customer rules apply. Published profiles are immutable; changes create a new version.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from mapping_engine.models import MappingDefinition, SourceFormat
from rules_engine.declarative import RuleConfig


class ProfileStatus(StrEnum):
    DRAFT = "DRAFT"
    TESTING = "TESTING"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class InputFormat(StrEnum):
    ISO20022_XML = "ISO20022_XML"
    CUSTOM_XML = "CUSTOM_XML"
    JSON = "JSON"
    CSV = "CSV"


class OutputFormat(StrEnum):
    ANALYSIS_JSON = "ANALYSIS_JSON"
    CANONICAL_JSON = "CANONICAL_JSON"
    CANDIDATE_XML = "CANDIDATE_XML"


class RetentionPolicy(StrEnum):
    ZERO = "ZERO"
    METADATA_ONLY = "METADATA_ONLY"
    CONFIGURED = "CONFIGURED"


class AddressCoverage(StrEnum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED_GEOGRAPHY = "UNSUPPORTED_GEOGRAPHY"
    UNKNOWN = "UNKNOWN"


def utcnow() -> datetime:
    return datetime.now(UTC)


class IntegrationProfile(BaseModel):
    """A mutable profile draft (the working copy)."""

    id: str | None = None
    organization_id: str
    name: str
    description: str = ""
    status: ProfileStatus = ProfileStatus.DRAFT
    input_format: InputFormat
    output_format: OutputFormat = OutputFormat.ANALYSIS_JSON
    retention_policy: RetentionPolicy = RetentionPolicy.METADATA_ONLY
    address_policy: str = "auto"  # auto | cloudnova | swift
    ai_policy: str = "disabled"
    allowed_messages: list[str] = Field(default_factory=list)
    mapping: MappingDefinition
    rules: list[RuleConfig] = Field(default_factory=list)
    version_number: int = 1
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    published_at: datetime | None = None

    @property
    def source_format(self) -> SourceFormat:
        return {
            InputFormat.JSON: SourceFormat.JSON,
            InputFormat.CSV: SourceFormat.CSV,
            InputFormat.CUSTOM_XML: SourceFormat.CUSTOM_XML,
        }.get(self.input_format, SourceFormat.JSON)

    @property
    def mapping_version(self) -> str:
        return self.mapping.mapping_version

    @property
    def ruleset_version(self) -> str:
        return "cloudnova-customer-v1"


class ProfileVersion(BaseModel):
    """An immutable published snapshot of a profile."""

    id: str
    profile_id: str
    organization_id: str
    version_number: int
    name: str
    input_format: InputFormat
    mapping: MappingDefinition
    rules: list[RuleConfig]
    mapping_version: str
    ruleset_version: str
    published_at: datetime = Field(default_factory=utcnow)
