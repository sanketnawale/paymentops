"""Deterministic, versioned rules engine.

Rules are deterministic, testable, and externalized from API code. Rules return stable
``RuleFinding`` records. There is no arbitrary Python execution from customer-supplied
config; rules are code with a fixed versioned ruleset.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum

from payment_domain.models import PaymentMessage, PaymentTransaction

# Version of the CloudNova rule set. Bump whenever rule logic changes.
RULESET_VERSION = "cloudnova-address-v1"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class RuleFinding:
    rule_id: str
    ruleset_version: str
    severity: Severity
    target: str  # XPath-like path of the affected element
    message: str
    evidence: list[str] = field(default_factory=list)
    suggested_action: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "ruleset_version": self.ruleset_version,
            "severity": self.severity.value,
            "target": self.target,
            "message": self.message,
            "evidence": self.evidence,
            "suggested_action": self.suggested_action,
        }


class Rule(ABC):
    rule_id: str = ""
    name: str = ""
    category: str = ""
    severity: Severity = Severity.WARNING
    ruleset_version: str = RULESET_VERSION

    @abstractmethod
    def evaluate(self, transaction: PaymentTransaction) -> list[RuleFinding]:
        raise NotImplementedError

    def _finding(
        self,
        transaction: PaymentTransaction,
        *,
        target: str,
        message: str,
        evidence: list[str],
        suggested_action: str | None = None,
    ) -> RuleFinding:
        return RuleFinding(
            rule_id=self.rule_id,
            ruleset_version=self.ruleset_version,
            severity=self.severity,
            target=target or (transaction.source_path or ""),
            message=message,
            evidence=evidence,
            suggested_action=suggested_action,
        )


class RuleEngine:
    """Evaluates a message against a set of versioned rules."""

    def __init__(self, rules: list[Rule], *, version: str = RULESET_VERSION) -> None:
        self._rules = rules
        self.version = version

    def evaluate(self, message: PaymentMessage) -> list[RuleFinding]:
        findings: list[RuleFinding] = []
        for tx in message.transactions:
            for rule in self._rules:
                findings.extend(rule.evaluate(tx))
        return findings
