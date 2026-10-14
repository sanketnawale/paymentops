"""Shared party/account/agent/address mapping for payment-transfer messages.

These helpers are used by the pacs.008, pain.001, and pacs.009 adapters because the party
semantics genuinely match (debtor/creditor, account, financial institution, postal address).
pacs.002 does NOT use these; it is a status report.
"""

from __future__ import annotations

from decimal import Decimal

from lxml import etree

from iso_engine.common import child, child_text, children, text
from payment_domain.models import (
    Account,
    FinancialInstitution,
    MonetaryAmount,
    Party,
    PostalAddress,
    RemittanceInformation,
)


def map_amount(el: etree._Element | None) -> MonetaryAmount | None:
    if el is None:
        return None
    value = text(el)
    if value is None:
        return None
    try:
        minor = int(round(Decimal(value) * 100))
    except Exception:  # noqa: BLE001 - best effort amount
        minor = 0
    return MonetaryAmount(amount_minor=minor, currency=el.get("Ccy") or "EUR")


def map_party(el: etree._Element | None, path: str) -> Party | None:
    if el is None:
        return None
    return Party(
        name=child_text(el, "Nm"),
        postal_address=map_address(child(el, "PstlAdr"), f"{path}/PstlAdr"),
        source_path=path,
    )


def map_account(el: etree._Element | None, path: str) -> Account | None:
    if el is None:
        return None
    id_el = child(el, "Id")
    iban = child_text(id_el, "IBAN")
    other = child_text(child(id_el, "Othr"), "Id")
    return Account(
        iban=iban,
        other_identification=other,
        name=child_text(el, "Nm"),
        source_path=path,
    )


def map_agent(el: etree._Element | None, path: str) -> FinancialInstitution | None:
    if el is None:
        return None
    fi = child(el, "FinInstnId")
    return FinancialInstitution(
        bic=child_text(fi, "BICFI"),
        clearing_system_member=child_text(child(fi, "ClrSysMmbId"), "MmbId"),
        name=child_text(fi, "Nm"),
        postal_address=map_address(child(fi, "PstlAdr"), f"{path}/FinInstnId/PstlAdr"),
        source_path=path,
    )


def map_remittance(el: etree._Element | None, path: str) -> RemittanceInformation | None:
    if el is None:
        return None
    unstructured = [t for t in (text(u) for u in children(el, "Ustrd")) if t]
    ref = child_text(child(el, "Strd"), "CdtrRefInf")
    return RemittanceInformation(
        unstructured=unstructured,
        reference=ref,
        source_path=path,
    )


def map_address(el: etree._Element | None, path: str) -> PostalAddress | None:
    if el is None:
        return None
    original_fields: dict[str, str] = {}
    for field_name in ("StrtNm", "BldgNb", "PstCd", "TwnNm", "Ctry"):
        value = child_text(el, field_name)
        if value:
            original_fields[field_name] = value
    address_lines = [t for t in (text(x) for x in children(el, "AdrLine")) if t]
    return PostalAddress(
        street_name=original_fields.get("StrtNm"),
        building_number=original_fields.get("BldgNb"),
        postcode=original_fields.get("PstCd"),
        town_name=original_fields.get("TwnNm"),
        country=original_fields.get("Ctry"),
        address_lines=address_lines,
        source_path=path,
        original_fields=original_fields,
        normalized_fields={},
    )
