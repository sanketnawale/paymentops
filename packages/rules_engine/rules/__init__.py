"""Rule registries."""

from __future__ import annotations

from rules_engine.base import RULESET_VERSION, Rule, RuleEngine
from rules_engine.rules.address_rules import (
    CountryMissingRule,
    HybridAddressRule,
    InvalidCountryCodeRule,
    TownMissingRule,
    UnstructuredAddressRule,
)
from rules_engine.rules.structural_rules import (
    MissingAmountRule,
    MissingCreditorAccountRule,
    MissingCreditorAgentBicRule,
    MissingDebtorAgentBicRule,
    MissingEndToEndIdRule,
    MissingInstructionIdRule,
)

# The versioned CloudNova address ruleset used for Week 2.
ADDRESS_RULESET: list[Rule] = [
    MissingInstructionIdRule(),
    MissingAmountRule(),
    MissingEndToEndIdRule(),
    MissingDebtorAgentBicRule(),
    MissingCreditorAgentBicRule(),
    MissingCreditorAccountRule(),
    TownMissingRule(),
    CountryMissingRule(),
    InvalidCountryCodeRule(),
    UnstructuredAddressRule(),
    HybridAddressRule(),
]


def build_address_ruleset() -> RuleEngine:
    return RuleEngine(ADDRESS_RULESET, version=RULESET_VERSION)


__all__ = [
    "ADDRESS_RULESET",
    "RuleEngine",
    "RULESET_VERSION",
    "build_address_ruleset",
]
