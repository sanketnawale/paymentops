"""pacs.009.001.13 -> canonical PaymentMessage adapter (FI-to-FI credit transfer).

This is NOT equivalent to pacs.008: debtor and creditor are financial institutions. The
adapter extracts transfer data, settlement metadata, and the FI party/agent structure.

Week 5 supports the core (FICdtTrf) variant. COV (cover) is exposed as source metadata, not
modelled as a separate underlying transfer.
"""

from __future__ import annotations

from lxml import etree

from iso_engine.common import child, child_text, children, parse_datetime
from iso_engine.pacs009.namespace import SupportedVersion
from iso_engine.parties import map_account, map_agent, map_amount
from payment_domain.models import (
    FinancialInstitution,
    Party,
    PaymentMessage,
    PaymentTransaction,
    SourceFormat,
    ValidationStatus,
)


def map_pacs009_to_canonical(root: etree._Element, version: SupportedVersion) -> PaymentMessage:
    msg_root = child(root, version.root_element)
    grp = child(msg_root, "GrpHdr")
    message_id = child_text(grp, "MsgId")
    creation = parse_datetime(child_text(grp, "CreDtTm"))
    sttlm_mtd = child_text(child(grp, "SttlmInf"), "SttlmMtd")

    transactions: list[PaymentTransaction] = []
    cov_indicators: list[str] = []
    for tx_el in children(msg_root, "CdtTrfTxInf"):
        path = "/FICdtTrf/CdtTrfTxInf"
        pmt_id = child(tx_el, "PmtId")
        amt = child(child(tx_el, "Amt"), "InstdAmt")
        cov_indicators.append("COV" if child(tx_el, "UndrlygCstmrCdtTrf") else "CORE")
        transactions.append(
            PaymentTransaction(
                instruction_id=child_text(pmt_id, "InstrId"),
                end_to_end_id=child_text(pmt_id, "EndToEndId"),
                transaction_id=child_text(pmt_id, "TxId"),
                amount=map_amount(amt),
                debtor=_fi_party(child(tx_el, "Dbtr"), f"{path}/Dbtr"),
                creditor=_fi_party(child(tx_el, "Cdtr"), f"{path}/Cdtr"),
                debtor_agent=map_agent(child(tx_el, "DbtrAgt"), f"{path}/DbtrAgt"),
                creditor_agent=map_agent(child(tx_el, "CdtrAgt"), f"{path}/CdtrAgt"),
                debtor_account=map_account(child(tx_el, "DbtrAcct"), f"{path}/DbtrAcct"),
                creditor_account=map_account(child(tx_el, "CdtrAcct"), f"{path}/CdtrAcct"),
                source_path=path,
            )
        )

    return PaymentMessage(
        message_type=version.identifier,
        message_id=message_id,
        creation_datetime=creation,
        transactions=transactions,
        source_format=SourceFormat.XML_PACS_009,
        validation_status=ValidationStatus.PENDING,
        source_metadata={
            "message_name": version.message_name,
            "settlement_method": sttlm_mtd or "",
            "variants": ",".join(cov_indicators),
        },
    )


def _fi_party(el: etree._Element | None, path: str) -> Party | None:
    """Map a FI party (Dbtr/Cdtr) which is a financial institution identifier."""
    if el is None:
        return None
    fi_el = child(el, "FinInstnId")
    return Party(
        name=child_text(fi_el, "Nm"),
        financial_institution=FinancialInstitution(
            bic=child_text(fi_el, "BICFI"),
            name=child_text(fi_el, "Nm"),
            source_path=path,
        ),
        source_path=path,
    )


def _intermediary_bics(tx_el: etree._Element) -> list[str]:
    bics: list[str] = []
    for name in ("IntrmyAgt1", "IntrmyAgt2", "IntrmyAgt3"):
        node = child(tx_el, name)
        bic = child_text(child(node, "FinInstnId"), "BICFI")
        if bic:
            bics.append(bic)
    return bics
