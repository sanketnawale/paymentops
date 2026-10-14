"""pain.001.001.13 -> canonical PaymentMessage adapter.

Raw pain.001 XML
  -> secure XML tree
  -> pain.001 adapter
  -> canonical PaymentMessage

This is the ONLY place that understands pain.001 XML structure. A pain.001 message may contain
multiple ``PmtInf`` blocks, each with multiple ``CdtTrfTxInf`` transactions; all transactions
are flattened into the canonical ``PaymentMessage``. Original values are preserved.
"""

from __future__ import annotations

from datetime import datetime

from lxml import etree

from iso_engine.common import child, child_text, children, parse_datetime
from iso_engine.pain001.namespace import SupportedVersion
from iso_engine.parties import (
    map_account,
    map_agent,
    map_amount,
    map_party,
    map_remittance,
)
from payment_domain.models import (
    PaymentMessage,
    PaymentTransaction,
    SourceFormat,
    ValidationStatus,
)


def map_pain001_to_canonical(root: etree._Element, version: SupportedVersion) -> PaymentMessage:
    msg_root = child(root, version.root_element)
    grp = child(msg_root, "GrpHdr")
    message_id = child_text(grp, "MsgId")
    creation = parse_datetime(child_text(grp, "CreDtTm"))

    transactions: list[PaymentTransaction] = []
    for pmt_inf in children(msg_root, "PmtInf"):
        pmt_inf_path = "/CstmrCdtTrfInitn/PmtInf"
        # PmtInf-level debtor details apply to all transactions in the block.
        debtor = map_party(child(pmt_inf, "Dbtr"), f"{pmt_inf_path}/Dbtr")
        debtor_account = map_account(child(pmt_inf, "DbtrAcct"), f"{pmt_inf_path}/DbtrAcct")
        debtor_agent = map_agent(child(pmt_inf, "DbtrAgt"), f"{pmt_inf_path}/DbtrAgt")
        reqd_exctn = child_text(pmt_inf, "ReqdExctnDt") or child_text(pmt_inf, "ReqdExctnDtTm")
        for tx_el in children(pmt_inf, "CdtTrfTxInf"):
            path = f"{pmt_inf_path}/CdtTrfTxInf"
            pmt_id = child(tx_el, "PmtId")
            amt = child(child(tx_el, "Amt"), "InstdAmt")
            transactions.append(
                PaymentTransaction(
                    instruction_id=child_text(pmt_id, "InstrId"),
                    end_to_end_id=child_text(pmt_id, "EndToEndId"),
                    transaction_id=child_text(pmt_id, "TxId"),
                    amount=map_amount(amt),
                    debtor=debtor,
                    creditor=map_party(child(tx_el, "Cdtr"), f"{path}/Cdtr"),
                    debtor_account=debtor_account,
                    creditor_account=map_account(child(tx_el, "CdtrAcct"), f"{path}/CdtrAcct"),
                    debtor_agent=debtor_agent,
                    creditor_agent=map_agent(child(tx_el, "CdtrAgt"), f"{path}/CdtrAgt"),
                    remittance=map_remittance(child(tx_el, "RmtInf"), f"{path}/RmtInf"),
                    requested_execution_date=_date_or_datetime(reqd_exctn),
                    source_path=path,
                )
            )

    return PaymentMessage(
        message_type=version.identifier,
        message_id=message_id,
        creation_datetime=creation,
        transactions=transactions,
        source_format=SourceFormat.XML_PAIN_001,
        validation_status=ValidationStatus.PENDING,
        source_metadata={"message_name": version.message_name},
    )


def _date_or_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return parse_datetime(value)
