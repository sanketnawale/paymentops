"""pacs.002.001.16 -> canonical LifecycleStatusReport adapter.

This message is fundamentally a STATUS REPORT. It is NOT mapped to a PaymentTransaction and
never treated as a new payment instruction. It produces a ``LifecycleStatusReport`` carrying
raw ISO status, normalized PaymentOps status, status reasons, and references to the original
payment message(s).
"""

from __future__ import annotations

from lxml import etree

from iso_engine.common import child, child_text, children, parse_datetime
from iso_engine.pacs002.namespace import SupportedVersion
from iso_engine.parties import map_amount
from payment_domain.models import (
    LifecycleStatusReport,
    PaymentStatus,
    RelatedPaymentReference,
    StatusReason,
    TransactionStatus,
)


def map_pacs002_to_status(root: etree._Element, version: SupportedVersion) -> LifecycleStatusReport:
    msg_root = child(root, version.root_element)
    grp = child(msg_root, "GrpHdr")
    orgnl_grp = child(msg_root, "OrgnlGrpInfAndSts")

    group_raw = child_text(orgnl_grp, "GrpSts")
    report = LifecycleStatusReport(
        message_family=version.identifier.split(".")[0],
        message_definition=version.message_name,
        message_version=version.identifier,
        namespace=version.namespace,
        message_id=child_text(grp, "MsgId"),
        creation_datetime=parse_datetime(child_text(grp, "CreDtTm")),
        original_message_id=child_text(orgnl_grp, "OrgnlMsgId"),
        original_message_definition=child_text(orgnl_grp, "OrgnlMsgNmId"),
        group_status_raw=group_raw,
        group_status=_normalize_status(group_raw),
    )

    for tx_el in children(msg_root, "TxInfAndSts"):
        raw = child_text(tx_el, "TxSts")
        orgnl_tx_ref = child(tx_el, "OrgnlTxRef")
        amount = map_amount(child(child(orgnl_tx_ref, "Amt"), "InstdAmt"))
        ref = _reference(orgnl_tx_ref)
        report.transaction_statuses.append(
            TransactionStatus(
                original_instruction_id=child_text(tx_el, "OrgnlInstrId"),
                original_end_to_end_id=child_text(tx_el, "OrgnlEndToEndId"),
                original_transaction_id=child_text(tx_el, "OrgnlTxId"),
                raw_iso_status=raw,
                normalized_status=_normalize_status(raw),
                reasons=_reasons(tx_el),
                amount=amount,
                reference=ref,
            )
        )
    return report


def _reasons(tx_el: etree._Element) -> list[StatusReason]:
    reasons: list[StatusReason] = []
    for inf in children(tx_el, "StsRsnInf"):
        rsn = child(inf, "Rsn")
        reasons.append(
            StatusReason(
                code=child_text(rsn, "Cd"),
                proprietary_code=child_text(rsn, "Prprtry"),
                additional_information=child_text(inf, "AddtlInf"),
                originator=child_text(inf, "Orgnl"),
                normalized_category=None,
            )
        )
    return reasons


def _reference(orgnl_tx_ref: etree._Element | None) -> RelatedPaymentReference | None:
    if orgnl_tx_ref is None:
        return None
    pmt_id = child(orgnl_tx_ref, "PmtId")
    return RelatedPaymentReference(
        instruction_id=child_text(pmt_id, "InstrId"),
        end_to_end_id=child_text(pmt_id, "EndToEndId"),
        transaction_id=child_text(pmt_id, "TxId"),
        amount=map_amount(child(child(orgnl_tx_ref, "Amt"), "InstdAmt")),
    )


def _normalize_status(raw: str | None) -> PaymentStatus:
    """Controlled mapping of raw ISO status codes to PaymentOps analytical statuses.

    Raw ISO code is always preserved separately. Unknown codes map to UNKNOWN.
    """
    if raw is None:
        return PaymentStatus.UNKNOWN
    accepted = {"ACCP", "ACSP", "ACWC", "ACSC", "ACCC"}
    if raw in accepted:
        return PaymentStatus.ACCEPTED
    if raw == "RCVD":
        return PaymentStatus.PROCESSING
    if raw == "PDNG":
        return PaymentStatus.PENDING
    if raw == "PART":
        return PaymentStatus.PARTIALLY_ACCEPTED
    if raw in {"RJCT", "CANC"}:
        return PaymentStatus.REJECTED
    return PaymentStatus.UNKNOWN
