"""Address-readiness and country rules (ADR-001..ADR-005)."""

from __future__ import annotations

from payment_domain.countries import is_valid_country_code
from payment_domain.models import PaymentTransaction, PostalAddress
from rules_engine.base import Rule, RuleFinding, Severity

_STRUCTURED_FIELDS = ("street_name", "building_number", "postcode", "town_name", "country")


def _addresses(transaction: PaymentTransaction) -> list[tuple[str, PostalAddress | None]]:
    pairs: list[tuple[str, PostalAddress | None]] = []
    for label, party in (("Dbtr", transaction.debtor), ("Cdtr", transaction.creditor)):
        if party and party.postal_address:
            pairs.append((label, party.postal_address))
    for label, agent in (
        ("DbtrAgt", transaction.debtor_agent),
        ("CdtrAgt", transaction.creditor_agent),
    ):
        if agent and agent.postal_address:
            pairs.append((label, agent.postal_address))
    return pairs


class TownMissingRule(Rule):
    rule_id = "ADR-001"
    name = "Town Name missing"
    category = "Address readiness"
    severity = Severity.WARNING

    def evaluate(self, transaction: PaymentTransaction) -> list[RuleFinding]:
        out: list[RuleFinding] = []
        for label, addr in _addresses(transaction):
            if addr is None:
                continue
            if addr.town_name is None and addr.country is not None:
                out.append(
                    self._finding(
                        transaction,
                        target=f"{label}/PstlAdr",
                        message="Town name is missing",
                        evidence=[f"{label}/PstlAdr/TwnNm is absent"],
                        suggested_action="Provide TwnNm or derive from address lines",
                    )
                )
        return out


class CountryMissingRule(Rule):
    rule_id = "ADR-002"
    name = "Country missing"
    category = "Address readiness"
    severity = Severity.ERROR

    def evaluate(self, transaction: PaymentTransaction) -> list[RuleFinding]:
        out: list[RuleFinding] = []
        for label, addr in _addresses(transaction):
            if addr is None:
                continue
            if addr.country is None:
                out.append(
                    self._finding(
                        transaction,
                        target=f"{label}/PstlAdr",
                        message="Country is missing",
                        evidence=[f"{label}/PstlAdr/Ctry is absent"],
                        suggested_action="Provide ISO 3166-1 alpha-2 Ctry",
                    )
                )
        return out


class InvalidCountryCodeRule(Rule):
    rule_id = "ADR-003"
    name = "Country code invalid"
    category = "Country normalization"
    severity = Severity.ERROR

    def evaluate(self, transaction: PaymentTransaction) -> list[RuleFinding]:
        out: list[RuleFinding] = []
        for label, addr in _addresses(transaction):
            if addr is None or addr.country is None:
                continue
            if not is_valid_country_code(addr.country):
                out.append(
                    self._finding(
                        transaction,
                        target=f"{label}/PstlAdr",
                        message="Country code is not a valid ISO 3166-1 alpha-2 code",
                        evidence=[f"Ctry='{addr.country}'"],
                        suggested_action="Normalise to ISO alpha-2 code",
                    )
                )
        return out


class UnstructuredAddressRule(Rule):
    rule_id = "ADR-004"
    name = "Address is unstructured"
    category = "Address readiness"
    severity = Severity.WARNING

    def evaluate(self, transaction: PaymentTransaction) -> list[RuleFinding]:
        out: list[RuleFinding] = []
        for label, addr in _addresses(transaction):
            if addr is None:
                continue
            has_structured = any(getattr(addr, f) for f in _STRUCTURED_FIELDS)
            if not has_structured and addr.address_lines:
                out.append(
                    self._finding(
                        transaction,
                        target=f"{label}/PstlAdr",
                        message="Address is unstructured and requires readiness review",
                        evidence=[f"{label}/PstlAdr contains only AdrLine"],
                        suggested_action="Structure address from AdrLine",
                    )
                )
        return out


class HybridAddressRule(Rule):
    rule_id = "ADR-005"
    name = "Mixed/hybrid address candidate"
    category = "Address readiness"
    severity = Severity.INFO

    def evaluate(self, transaction: PaymentTransaction) -> list[RuleFinding]:
        out: list[RuleFinding] = []
        for label, addr in _addresses(transaction):
            if addr is None:
                continue
            has_structured = any(getattr(addr, f) for f in _STRUCTURED_FIELDS)
            if has_structured and addr.address_lines:
                out.append(
                    self._finding(
                        transaction,
                        target=f"{label}/PstlAdr",
                        message="Hybrid address (structured + AdrLine) requires evaluation",
                        evidence=[f"{label}/PstlAdr has both structured fields and AdrLine"],
                    )
                )
        return out
