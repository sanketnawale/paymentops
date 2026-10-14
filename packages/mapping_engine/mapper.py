"""Controlled mapper: source records -> canonical PaymentMessage.

Applies declarative field mappings with safe transforms. No arbitrary code execution. Missing
REQUIRED source fields produce a structured MAP-001 finding (never silently null).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

from lxml import etree

from mapping_engine.models import (
    FieldRequirement,
    MappingDefinition,
    MappingIssue,
    MappingResult,
    MappingSeverity,
)
from mapping_engine.selectors import resolve_json_path, resolve_xpath
from mapping_engine.transforms import transform
from payment_domain.models import (
    Account,
    FinancialInstitution,
    MonetaryAmount,
    Party,
    PaymentMessage,
    PaymentTransaction,
    PostalAddress,
    RemittanceInformation,
    SourceFormat,
)


def map_to_canonical(definition: MappingDefinition, source: Any) -> MappingResult:
    """Map a source payload (JSON/CSV/XML) into a canonical ``PaymentMessage``."""
    records = _extract_records(definition, source)
    transactions: list[PaymentTransaction] = []
    issues: list[MappingIssue] = []

    for i, record in enumerate(records):
        tx = PaymentTransaction()
        for fm in definition.fields:
            value = _get_value(record, fm.source)
            if value is None or value == "":
                if fm.required == FieldRequirement.REQUIRED:
                    issues.append(
                        MappingIssue(
                            code="MAP-001",
                            severity=MappingSeverity.ERROR,
                            message="Required source field missing",
                            path=fm.target,
                        )
                    )
                    continue
                if fm.default is not None:
                    value = fm.default
                else:
                    continue
            value = _apply_transforms(value, fm.transforms)
            _set_target(tx, fm.target, value, prefix=f"transactions[{i}]")
        transactions.append(tx)

    message = PaymentMessage(
        message_type=definition.source_format.value,
        source_format=_source_format(definition.source_format),
        transactions=transactions,
    )
    return MappingResult(message=message, mapping_version=definition.mapping_version, issues=issues)


def _extract_records(definition: MappingDefinition, source: Any) -> list[Any]:
    if definition.source_format.value == "csv":
        if isinstance(source, list):
            return source
        return []
    if definition.source_format.value == "json":
        if definition.record_selector:
            return resolve_json_path(source, definition.record_selector)
        return [source] if isinstance(source, dict) else []
    if definition.source_format.value == "custom_xml":
        if isinstance(source, etree._Element) and definition.record_selector:
            return list(cast(list[Any], source.xpath(definition.record_selector)))
        return []
    return []


def _get_value(record: Any, source: str) -> Any:
    if isinstance(record, dict):
        values = (
            resolve_json_path(record, source) if source.startswith("$") else [record.get(source)]
        )
        return values[0] if values else None
    if isinstance(record, etree._Element):
        values = resolve_xpath(record, source)
        return values[0] if values else None
    return None


def _apply_transforms(value: Any, transforms: list[str]) -> Any:
    for name in transforms:
        value = transform(name, value)
    return value


def _source_format(value: str) -> SourceFormat:
    return {
        "json": SourceFormat.JSON,
        "csv": SourceFormat.CSV,
        "custom_xml": SourceFormat.XML_PAIN_001,
    }.get(value, SourceFormat.UNKNOWN)


def _set_target(tx: PaymentTransaction, target: str, value: Any, *, prefix: str) -> None:
    seg = [s for s in target.split(".") if s]
    if not seg:
        return
    if seg[0] == "amount" and len(seg) >= 2:
        tx.amount = tx.amount or MonetaryAmount()
        if seg[1] == "amount_minor":
            tx.amount.amount_minor = _to_minor(value)
        elif seg[1] == "currency":
            tx.amount.currency = str(value)[:3].upper()
        return
    if seg[0] == "instruction_id":
        tx.instruction_id = str(value)
    elif seg[0] == "end_to_end_id":
        tx.end_to_end_id = str(value)
    elif seg[0] == "transaction_id":
        tx.transaction_id = str(value)
    elif seg[0] == "debtor":
        _set_party(tx.debtor or Party(), seg[1:], value, tx, prefix, "Dbtr")
    elif seg[0] == "creditor":
        _set_party(tx.creditor or Party(), seg[1:], value, tx, prefix, "Cdtr")
    elif seg[0] == "debtor_account":
        tx.debtor_account = tx.debtor_account or Account()
        _set_account(tx.debtor_account, seg[1:], value)
    elif seg[0] == "creditor_account":
        tx.creditor_account = tx.creditor_account or Account()
        _set_account(tx.creditor_account, seg[1:], value)
    elif seg[0] == "debtor_agent":
        tx.debtor_agent = tx.debtor_agent or FinancialInstitution()
        _set_agent(tx.debtor_agent, seg[1:], value)
    elif seg[0] == "creditor_agent":
        tx.creditor_agent = tx.creditor_agent or FinancialInstitution()
        _set_agent(tx.creditor_agent, seg[1:], value)
    elif seg[0] == "remittance":
        tx.remittance = tx.remittance or RemittanceInformation()
        if len(seg) >= 2 and seg[1] == "unstructured":
            tx.remittance.unstructured.append(str(value))


def _set_party(
    party: Party, seg: list[str], value: Any, tx: PaymentTransaction, prefix: str, label: str
) -> None:
    if not seg:
        return
    if seg[0] == "name":
        party.name = str(value)
    elif seg[0] == "postal_address":
        addr = party.postal_address or PostalAddress()
        _set_address(addr, seg[1:], value, f"{prefix}/{label}/PstlAdr")
        party.postal_address = addr
    if label == "Dbtr":
        tx.debtor = party
    else:
        tx.creditor = party


def _set_address(addr: PostalAddress, seg: list[str], value: Any, path: str) -> None:
    if not seg:
        return
    addr.source_path = path
    field = seg[0]
    if field == "street_name":
        addr.street_name = str(value)
    elif field == "building_number":
        addr.building_number = str(value)
    elif field == "postcode":
        addr.postcode = str(value)
    elif field == "town_name":
        addr.town_name = str(value)
    elif field == "country":
        addr.country = str(value)
        addr.original_fields["Ctry"] = str(value)
    elif field == "address_lines":
        addr.address_lines.append(str(value))


def _set_account(account: Account, seg: list[str], value: Any) -> None:
    if not seg:
        return
    if seg[0] == "iban":
        account.iban = str(value)
    elif seg[0] == "name":
        account.name = str(value)
    elif seg[0] == "other_identification":
        account.other_identification = str(value)


def _set_agent(agent: FinancialInstitution, seg: list[str], value: Any) -> None:
    if not seg:
        return
    if seg[0] == "bic":
        agent.bic = str(value)
    elif seg[0] == "name":
        agent.name = str(value)


def _to_minor(value: Any) -> int:
    if isinstance(value, Decimal):
        return int(round(value * 100))
    if isinstance(value, (int, float)):
        return int(round(float(value) * 100))
    if isinstance(value, str):
        try:
            return int(round(Decimal(value.strip().replace(",", ".")) * 100))
        except Exception:  # noqa: BLE001
            return 0
    return 0
