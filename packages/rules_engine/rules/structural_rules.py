"""Structural and basic semantic consistency rules (ISO-xxx, SEM-xxx)."""

from __future__ import annotations

from payment_domain.models import PaymentTransaction
from rules_engine.base import Rule, RuleFinding, Severity


class MissingInstructionIdRule(Rule):
    rule_id = "ISO-001"
    name = "Instruction ID missing"
    category = "ISO / structural"
    severity = Severity.WARNING

    def evaluate(self, transaction: PaymentTransaction) -> list[RuleFinding]:
        if not transaction.instruction_id:
            return [
                self._finding(
                    transaction,
                    target=f"{transaction.source_path}/PmtId",
                    message="Payment instruction ID (InstrId) is missing",
                    evidence=["PmtId/InstrId is absent"],
                )
            ]
        return []


class MissingAmountRule(Rule):
    rule_id = "ISO-002"
    name = "Amount missing"
    category = "ISO / structural"
    severity = Severity.ERROR

    def evaluate(self, transaction: PaymentTransaction) -> list[RuleFinding]:
        if transaction.amount is None or transaction.amount.amount_minor <= 0:
            return [
                self._finding(
                    transaction,
                    target=f"{transaction.source_path}/Amt",
                    message="Amount is missing or non-positive",
                    evidence=["Amt/InstdAmt is absent or zero"],
                )
            ]
        return []


class MissingEndToEndIdRule(Rule):
    rule_id = "ISO-003"
    name = "End-to-end ID missing"
    category = "ISO / structural"
    severity = Severity.INFO

    def evaluate(self, transaction: PaymentTransaction) -> list[RuleFinding]:
        if not transaction.end_to_end_id:
            return [
                self._finding(
                    transaction,
                    target=f"{transaction.source_path}/PmtId",
                    message="End-to-end ID (EndToEndId) is missing",
                    evidence=["PmtId/EndToEndId is absent"],
                )
            ]
        return []


class MissingDebtorAgentBicRule(Rule):
    rule_id = "SEM-001"
    name = "Debtor agent BIC missing"
    category = "Basic semantic consistency"
    severity = Severity.WARNING

    def evaluate(self, transaction: PaymentTransaction) -> list[RuleFinding]:
        if transaction.debtor_agent and not transaction.debtor_agent.bic:
            return [
                self._finding(
                    transaction,
                    target=f"{transaction.source_path}/DbtrAgt",
                    message="Debtor agent BIC is missing",
                    evidence=["DbtrAgt/FinInstnId/BICFI is absent"],
                )
            ]
        return []


class MissingCreditorAgentBicRule(Rule):
    rule_id = "SEM-002"
    name = "Creditor agent BIC missing"
    category = "Basic semantic consistency"
    severity = Severity.WARNING

    def evaluate(self, transaction: PaymentTransaction) -> list[RuleFinding]:
        if transaction.creditor_agent and not transaction.creditor_agent.bic:
            return [
                self._finding(
                    transaction,
                    target=f"{transaction.source_path}/CdtrAgt",
                    message="Creditor agent BIC is missing",
                    evidence=["CdtrAgt/FinInstnId/BICFI is absent"],
                )
            ]
        return []


class MissingCreditorAccountRule(Rule):
    rule_id = "SEM-003"
    name = "Creditor account missing"
    category = "Basic semantic consistency"
    severity = Severity.WARNING

    def evaluate(self, transaction: PaymentTransaction) -> list[RuleFinding]:
        if transaction.creditor_account and not (
            transaction.creditor_account.iban or transaction.creditor_account.other_identification
        ):
            return [
                self._finding(
                    transaction,
                    target=f"{transaction.source_path}/CdtrAcct",
                    message="Creditor account identification missing",
                    evidence=["CdtrAcct/Id is empty"],
                )
            ]
        return []
