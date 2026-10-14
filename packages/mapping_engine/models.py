"""Mapping engine domain models (declarative, data-driven; no code execution)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel, Field

from payment_domain.models import PaymentMessage


class SourceFormat(StrEnum):
    JSON = "json"
    CSV = "csv"
    CUSTOM_XML = "custom_xml"


class FieldRequirement(StrEnum):
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"
    CONDITIONAL = "CONDITIONAL"


class MappingSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class FieldMapping(BaseModel):
    """A single source -> canonical target field mapping."""

    source: str
    target: str
    required: FieldRequirement = FieldRequirement.OPTIONAL
    transforms: list[str] = Field(default_factory=list)
    default: str | None = None


class MappingDefinition(BaseModel):
    """A declarative mapping definition (data). Produces PaymentMessage from source records."""

    mapping_version: str
    source_format: SourceFormat
    record_selector: str | None = None  # JSONPath array / XPath nodeset / empty for CSV
    fields: list[FieldMapping] = Field(default_factory=list)


@dataclass(frozen=True)
class MappingIssue:
    code: str
    severity: MappingSeverity
    message: str
    path: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "path": self.path,
        }


@dataclass
class MappingResult:
    message: PaymentMessage
    mapping_version: str
    issues: list[MappingIssue] = field(default_factory=list)
