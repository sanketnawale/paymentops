"""CloudNova rules engine: deterministic, versioned, customer-independent.

Rules are externalized from the API layer. No arbitrary Python execution from customer
input; rules are code with a fixed versioned ruleset, plus declarative customer rules
(data-driven, allowlisted operators).
"""

from __future__ import annotations

from rules_engine.base import (
    RULESET_VERSION,
    Rule,
    RuleEngine,
    RuleFinding,
    Severity,
)
from rules_engine.declarative import (
    CLOUDNOVA_DEFAULT,
    CUSTOMER_CONFIGURABLE,
    OPERATORS,
    SYSTEM_MANDATORY,
    CompositeRuleEngine,
    DeclarativeRule,
    RuleConfig,
    build_declarative_rules,
    validate_rule_config,
)
from rules_engine.rules import ADDRESS_RULESET, build_address_ruleset

__all__ = [
    "ADDRESS_RULESET",
    "CLOUDNOVA_DEFAULT",
    "CUSTOMER_CONFIGURABLE",
    "OPERATORS",
    "RULESET_VERSION",
    "SYSTEM_MANDATORY",
    "CompositeRuleEngine",
    "DeclarativeRule",
    "Rule",
    "RuleConfig",
    "RuleEngine",
    "RuleFinding",
    "Severity",
    "build_address_ruleset",
    "build_declarative_rules",
    "validate_rule_config",
]
