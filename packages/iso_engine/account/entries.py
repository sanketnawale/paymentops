"""Shared camt entry/account/balance mapping.

camt.053 and camt.054 share the same ``Ntry`` structure, so this module is the single place
that understands it. Both adapters normalize into the same canonical ``AccountEntry``.
"""

from __future__ import annotations

from datetime import date

from lxml import etree

from iso_engine.common import child, child_text, children, text
from iso_engine.parties import map_amount, map_party
from payment_domain.models import (
    AccountBalance,
    AccountEntry,
    AccountReference,
    BalanceType,
    BankTransactionCode,
    CreditDebitIndicator,
)


def map_account(el: etree._Element | None) -> AccountReference | None:
    if el is None:
        return None
    id_el = child(el, "Id")
    iban = child_text(id_el, "IBAN")
    other = child_text(child(id_el, "Othr"), "Id")
    servicer = child(el, "Svcr")
    bic = child_text(child(servicer, "FinInstnId"), "BICFI") if servicer is not None else None
    return AccountReference(
        iban=iban,
        other_identification=other,
        currency=child_text(el, "Ccy"),
        name=child_text(el, "Nm"),
        servicer_bic=bic,
    )


def map_balance(el: etree._Element | None) -> AccountBalance | None:
    if el is None:
        return None
    tp = child(el, "Tp")
    code = child_text(child(tp, "CdOrPrtry"), "Cd") or child_text(tp, "Cd")
    if code is None:
        return None
    try:
        balance_type = BalanceType(code)
    except ValueError:
        return None
    amt = map_amount(child(el, "Amt"))
    if amt is None:
        return None
    cdi = child_text(el, "CdtDbtInd")
    return AccountBalance(
        type=balance_type,
        amount=amt,
        credit_debit=CreditDebitIndicator(cdi)
        if cdi in ("CRDT", "DBIT")
        else CreditDebitIndicator.CRDT,
    )


def map_entry(el: etree._Element, path: str) -> AccountEntry:
    """Map a camt ``Ntry`` element into a canonical ``AccountEntry``."""
    amount_el = child(el, "Amt")
    amount = map_amount(amount_el)
    cdi = child_text(el, "CdtDbtInd")

    tx_dtls = child(el, "NtryDtls")
    tx = child(tx_dtls, "TxDtls")
    refs = child(tx, "Refs")

    status_el = child(el, "Sts")

    return AccountEntry(
        entry_reference=child_text(el, "NtryRef"),
        account_servicer_reference=child_text(el, "AcctSvcrRef"),
        transaction_id=child_text(refs, "TxId"),
        instruction_id=child_text(refs, "InstrId"),
        end_to_end_id=child_text(refs, "EndToEndId"),
        uetr=child_text(refs, "UETR"),
        amount=amount,
        currency=(amount.currency if amount else None)
        or (amount_el.get("Ccy") if amount_el is not None else None),
        credit_debit=CreditDebitIndicator(cdi) if cdi in ("CRDT", "DBIT") else None,
        booking_date=_date(child(el, "BookgDt")),
        value_date=_date(child(el, "ValDt")),
        status=text(status_el) or child_text(status_el, "Cd"),
        bank_transaction_code=_bank_tx_code(child(el, "BkTxCd")),
        remittance_reference=_remittance(tx),
        debtor=map_party(
            child(child(tx, "RltdPties"), "Dbtr"), f"{path}/NtryDtls/TxDtls/RltdPties/Dbtr"
        ),
        creditor=map_party(
            child(child(tx, "RltdPties"), "Cdtr"), f"{path}/NtryDtls/TxDtls/RltdPties/Cdtr"
        ),
        related_agents=_related_agents(tx),
        original_message_reference=child_text(child(tx, "Refs"), "AcctSvcrRef"),
    )


def _bank_tx_code(el: etree._Element | None) -> BankTransactionCode | None:
    if el is None:
        return None
    domn = child(el, "Domn")
    fmly = child(domn, "Fmly")
    return BankTransactionCode(
        code=child_text(domn, "Cd"),
        family=child_text(fmly, "Cd"),
        sub_family=child_text(fmly, "SubFmlyCd"),
        proprietary=child_text(child(el, "Prtry"), "Cd"),
    )


def _remittance(tx: etree._Element | None) -> str | None:
    rmt = child(tx, "RmtInf")
    lines = children(rmt, "Ustrd")
    return text(lines[0]) if lines else None


def _related_agents(tx: etree._Element | None) -> list[str]:
    agts = child(tx, "RltdAgts")
    result: list[str] = []
    for name in ("DbtrAgt", "CdtrAgt"):
        node = child(agts, name)
        bic = child_text(child(node, "FinInstnId"), "BICFI") if node is not None else None
        if bic:
            result.append(bic)
    return result


def _date(el: etree._Element | None) -> date | None:
    if el is None:
        return None
    value = child_text(el, "Dt") or child_text(el, "DtTm")
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
