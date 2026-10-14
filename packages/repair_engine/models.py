"""Repair candidate and structured diff models.

Terminology: outputs are ``RepairCandidate`` until deterministic validation succeeds, then
``CandidateStatus.VALIDATED``. They are never presented as "corrected payments" before that.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from iso_engine.xsd_validator import SchemaValidationResult
from payment_domain.models import CandidateStatus
from rules_engine.base import RuleFinding


class ChangeStatus(StrEnum):
    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"


class ChangeSource(StrEnum):
    ADDRESS_PROVIDER = "ADDRESS_PROVIDER"
    RULE = "RULE"
    NORMALIZATION = "NORMALIZATION"
    MANUAL = "MANUAL"


@dataclass(frozen=True)
class DiffEntry:
    """A single structured change proposal."""

    path: str
    before: str | None
    after: str | None
    source: ChangeSource
    status: ChangeStatus = ChangeStatus.PROPOSED

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "before": self.before,
            "after": self.after,
            "source": self.source.value,
            "status": self.status.value,
        }


@dataclass
class RepairCandidate:
    """A candidate repair of the input message, awaiting deterministic validation."""

    candidate_id: str
    changes: list[DiffEntry] = field(default_factory=list)
    xml: str | None = None
    status: CandidateStatus = CandidateStatus.PROPOSED
    xsd_result: SchemaValidationResult | None = None
    rule_findings: list[RuleFinding] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    note: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "status": self.status.value,
            "changes": [c.to_dict() for c in self.changes],
            "xsd_valid": self.xsd_result.valid if self.xsd_result else None,
            "rule_findings": [f.to_dict() for f in self.rule_findings],
            "note": self.note,
        }
