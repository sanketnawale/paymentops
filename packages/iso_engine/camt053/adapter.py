"""camt.053.001.14 -> canonical AccountReportBundle adapter.

BankToCustomerStatementV14. A camt.053 is an account statement (balances + booked entries),
NOT a payment instruction. It produces canonical ``AccountEntry`` records that are reconciled
against payment lifecycles. Multiple statements and entries are supported.
"""

from __future__ import annotations

from datetime import date

from lxml import etree

from iso_engine.account.entries import map_account, map_balance, map_entry
from iso_engine.camt053.namespace import SupportedVersion
from iso_engine.common import child, child_text, children, parse_datetime
from payment_domain.models import (
    AccountReport,
    AccountReportBundle,
    AccountReportType,
)


def map_camt053_to_account_report(
    root: etree._Element, version: SupportedVersion
) -> AccountReportBundle:
    msg_root = child(root, "BkToCstmrStmt")
    grp = child(msg_root, "GrpHdr")
    reports: list[AccountReport] = []

    for stmt in children(msg_root, "Stmt"):
        path = "/BkToCstmrStmt/Stmt"
        account = map_account(child(stmt, "Acct"))
        balances = [b for b in (map_balance(bal) for bal in children(stmt, "Bal")) if b]
        entries = [map_entry(entry_el, f"{path}/Ntry") for entry_el in children(stmt, "Ntry")]
        period = child(stmt, "FrToDt")
        reports.append(
            AccountReport(
                message_family="camt",
                message_definition=version.message_name,
                message_version=version.identifier,
                namespace=version.namespace,
                message_id=child_text(grp, "MsgId"),
                creation_datetime=parse_datetime(child_text(grp, "CreDtTm")),
                report_type=AccountReportType.STATEMENT,
                account=account,
                statement_id=child_text(stmt, "Id"),
                period_start=_date(child(period, "FrDtTm")) or _date(child(period, "FrDt")),
                period_end=_date(child(period, "ToDtTm")) or _date(child(period, "ToDt")),
                balances=balances,
                entries=entries,
            )
        )

    return AccountReportBundle(
        message_family="camt",
        message_definition=version.message_name,
        message_version=version.identifier,
        namespace=version.namespace,
        message_id=child_text(grp, "MsgId"),
        creation_datetime=parse_datetime(child_text(grp, "CreDtTm")),
        report_type=AccountReportType.STATEMENT,
        reports=reports,
    )


def _date(el: etree._Element | None) -> date | None:
    if el is None:
        return None
    value = (el.text or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
