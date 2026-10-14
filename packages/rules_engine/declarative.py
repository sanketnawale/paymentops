"""Declarative, data-driven customer rules.

Rules are configuration (dict/JSON), never code. Operators are explicitly allowlisted. The
engine resolves a canonical field path on a transaction and applies the operator. Customers
may not disable critical/system rules (see overlay.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from payment_domain.models import PaymentTransaction
from rules_engine.base import RULESET_VERSION, Rule, RuleEngine, RuleFinding, Severity

# Allowlisted operators.
OPERATORS = {
    "in",
    "not_in",
    "equals",
    "not_equals",
    "is_empty",
    "not_empty",
    "greater_than",
    "less_than",
    "contains",
    "starts_with",
}

# Rule classification.
SYSTEM_MANDATORY = "SYSTEM_MANDATORY"
CLOUDNOVA_DEFAULT = "CLOUDNOVA_DEFAULT"
CUSTOMER_CONFIGURABLE = "CUSTOMER_CONFIGURABLE"


@dataclass(frozen=True)
class RuleConfig:
    rule_id: str
    field: str
    operator: str
    value: object
    severity: Severity = Severity.WARNING
    message: str | None = None
    category: str = "customer"
    classification: str = CUSTOMER_CONFIGURABLE
    ruleset_version: str = "cloudnova-customer-v1"

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> RuleConfig:
        return cls(
            rule_id=str(d["rule_id"]),
            field=str(d["field"]),
            operator=str(d["operator"]),
            value=d.get("value"),
            severity=Severity(str(d.get("severity", "WARNING"))),
            message=cast(str | None, d.get("message")),
            category=str(d.get("category", "customer")),
            classification=str(d.get("classification", CUSTOMER_CONFIGURABLE)),
            ruleset_version=str(d.get("ruleset_version", "cloudnova-customer-v1")),
        )


def validate_rule_config(config: RuleConfig) -> list[str]:
    errors: list[str] = []
    if config.operator not in OPERATORS:
        errors.append(f"unsupported operator '{config.operator}'")
    if config.classification == SYSTEM_MANDATORY:
        errors.append("customer config cannot declare SYSTEM_MANDATORY")
    return errors


class DeclarativeRule(Rule):
    """A single data-driven rule."""

    def __init__(self, config: RuleConfig) -> None:
        self.config = config
        self.rule_id = config.rule_id
        self.name = config.rule_id
        self.category = config.category
        self.severity = config.severity
        self.ruleset_version = config.ruleset_version

    def evaluate(self, transaction: PaymentTransaction) -> list[RuleFinding]:
        resolved = resolve_field(transaction, self.config.field)
        if _matches(resolved, self.config.operator, self.config.value):
            return [
                RuleFinding(
                    rule_id=self.rule_id,
                    ruleset_version=self.ruleset_version,
                    severity=self.severity,
                    target=self.config.field,
                    message=self.config.message or f"Rule {self.rule_id} triggered",
                    evidence=[f"field='{self.config.field}' value={resolved!r}"],
                )
            ]
        return []


def build_declarative_rules(rule_configs: list[RuleConfig]) -> list[Rule]:
    return [DeclarativeRule(c) for c in rule_configs]


def _matches(value: object, operator: str, expected: object) -> bool:
    if operator == "in":
        return value in expected if isinstance(expected, (list, tuple, set)) else False
    if operator == "not_in":
        return value not in expected if isinstance(expected, (list, tuple, set)) else False
    if operator == "equals":
        return value == expected
    if operator == "not_equals":
        return value != expected
    if operator == "is_empty":
        return value is None or value == ""
    if operator == "not_empty":
        return value is not None and value != ""
    if operator == "greater_than":
        v = _num(value)
        e = _num(expected)
        return v is not None and e is not None and v > e
    if operator == "less_than":
        v = _num(value)
        e = _num(expected)
        return v is not None and e is not None and v < e
    if operator == "contains":
        return isinstance(value, str) and isinstance(expected, str) and expected in value
    if operator == "starts_with":
        return isinstance(value, str) and value.startswith(str(expected))
    return False


def _num(value: object) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def resolve_field(transaction: PaymentTransaction, path: str) -> object:
    """Resolve a canonical field path on a transaction (e.g. 'creditor.postal_address.country')."""
    seg = [s for s in path.split(".") if s]
    node: object = transaction
    for s in seg:
        if node is None:
            return None
        node = _get_attr(node, s)
    return node


def _get_attr(obj: object, name: str) -> object:
    if hasattr(obj, name):
        return getattr(obj, name)
    return None


class CompositeRuleEngine(RuleEngine):
    """Runs CloudNova baseline + organization overlay + profile overlay rules.

    System/CloudNova rules always run; customer rules are appended. Evaluation order is
    deterministic. This implements the resolution concept (baseline -> org -> profile).
    """

    def __init__(
        self,
        baseline_rules: list[Rule],
        *,
        version: str = RULESET_VERSION,
        org_rules: list[Rule] | None = None,
        profile_rules: list[Rule] | None = None,
    ) -> None:
        super().__init__(
            [*baseline_rules, *(org_rules or []), *(profile_rules or [])],
            version=version,
        )
