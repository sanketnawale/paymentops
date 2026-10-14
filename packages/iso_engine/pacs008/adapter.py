"""pacs.008 -> canonical PaymentMessage adapter.

Raw pacs.008 XML
  -> secure XML tree
  -> pacs.008 adapter
  -> canonical PaymentMessage

This is the ONLY place that understands pacs.008 XML structure. Downstream logic works on
the canonical model. Original element values are preserved; nothing is silently normalized
away here (normalization is a separate, later stage).
"""

from __future__ import annotations

from datetime import datetime

from lxml import etree

from iso_engine.pacs008.namespace import SupportedVersion
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
    ValidationStatus,
)


def map_pacs008_to_canonical(root: etree._Element, version: SupportedVersion) -> PaymentMessage:
    msg_root = _child(root, "FIToFICstmrCdtTrf")
    grp = _child(msg_root, "GrpHdr")

    message_id = _text(_child(grp, "MsgId"))
    creation = _text(_child(grp, "CreDtTm"))

    transactions = [
        _map_transaction(tx, index) for index, tx in enumerate(_children(msg_root, "CdtTrfTxInf"))
    ]

    return PaymentMessage(
        message_type=version.identifier,
        message_id=message_id,
        creation_datetime=_parse_datetime(creation),
        transactions=transactions,
        source_format=SourceFormat.XML_PACS_008,
        validation_status=ValidationStatus.PENDING,
        source_metadata={"message_name": version.message_name},
    )


def _map_transaction(tx: etree._Element, index: int) -> PaymentTransaction:
    path = f"/Document/FIToFICstmrCdtTrf/CdtTrfTxInf[{index}]"
    pmt = _child(tx, "PmtId")
    amt = _child(_child(tx, "Amt"), "InstdAmt")

    return PaymentTransaction(
        instruction_id=_text(_child(pmt, "InstrId")),
        end_to_end_id=_text(_child(pmt, "EndToEndId")),
        transaction_id=_text(_child(pmt, "TxId")),
        amount=_map_amount(amt),
        debtor=_map_party(_child(tx, "Dbtr"), f"{path}/Dbtr"),
        creditor=_map_party(_child(tx, "Cdtr"), f"{path}/Cdtr"),
        debtor_account=_map_account(_child(tx, "DbtrAcct"), f"{path}/DbtrAcct"),
        creditor_account=_map_account(_child(tx, "CdtrAcct"), f"{path}/CdtrAcct"),
        debtor_agent=_map_agent(_child(tx, "DbtrAgt"), f"{path}/DbtrAgt"),
        creditor_agent=_map_agent(_child(tx, "CdtrAgt"), f"{path}/CdtrAgt"),
        remittance=_map_remittance(_child(tx, "RmtInf"), f"{path}/RmtInf"),
        source_path=path,
    )


def _map_amount(amt_el: etree._Element | None) -> MonetaryAmount | None:
    if amt_el is None:
        return None
    text = (amt_el.text or "0").strip()
    try:
        minor = int(round(float(text) * 100))
    except ValueError:
        minor = 0
    return MonetaryAmount(amount_minor=minor, currency=amt_el.get("Ccy") or "EUR")


def _map_party(el: etree._Element | None, path: str) -> Party | None:
    if el is None:
        return None
    return Party(
        name=_text(_child(el, "Nm")),
        postal_address=_map_address(_child(el, "PstlAdr"), f"{path}/PstlAdr"),
        source_path=path,
    )


def _map_account(el: etree._Element | None, path: str) -> Account | None:
    if el is None:
        return None
    id_el = _child(el, "Id")
    iban = _text(_child(id_el, "IBAN"))
    other = _text(_child(_child(id_el, "Othr"), "Id"))
    return Account(
        iban=iban,
        other_identification=other,
        name=_text(_child(el, "Nm")),
        source_path=path,
    )


def _map_agent(el: etree._Element | None, path: str) -> FinancialInstitution | None:
    if el is None:
        return None
    fi = _child(el, "FinInstnId")
    return FinancialInstitution(
        bic=_text(_child(fi, "BICFI")),
        clearing_system_member=_text(_child(_child(fi, "ClrSysMmbId"), "MmbId")),
        name=_text(_child(fi, "Nm")),
        postal_address=_map_address(_child(fi, "PstlAdr"), f"{path}/FinInstnId/PstlAdr"),
        source_path=path,
    )


def _map_remittance(el: etree._Element | None, path: str) -> RemittanceInformation | None:
    if el is None:
        return None
    unstructured = [_text(u) for u in _children(el, "Ustrd") if _text(u) is not None]
    return RemittanceInformation(
        unstructured=unstructured,
        source_path=path,
    )


def _map_address(el: etree._Element | None, path: str) -> PostalAddress | None:
    if el is None:
        return None
    original_fields: dict[str, str] = {}
    for field_name in ("StrtNm", "BldgNb", "PstCd", "TwnNm", "Ctry"):
        value = _text(_child(el, field_name))
        if value:
            original_fields[field_name] = value

    address_lines = [t for t in (_text(x) for x in _children(el, "AdrLine")) if t]

    return PostalAddress(
        street_name=original_fields.get("StrtNm"),
        building_number=original_fields.get("BldgNb"),
        postcode=original_fields.get("PstCd"),
        town_name=original_fields.get("TwnNm"),
        country=original_fields.get("Ctry"),
        country_name=None,
        address_lines=address_lines,
        source_path=path,
        original_fields=original_fields,
        normalized_fields={},
    )


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


# --- lxml helpers (namespace-agnostic by local name) ---


def _children(el: etree._Element | None, name: str) -> list[etree._Element]:
    if el is None:
        return []
    return [c for c in el if _local(c.tag) == name]


def _child(el: etree._Element | None, name: str) -> etree._Element | None:
    for c in _children(el, name):
        return c
    return None


def _local(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _text(el: etree._Element | None) -> str | None:
    if el is None or el.text is None:
        return None
    value = el.text.strip()
    return value or None
