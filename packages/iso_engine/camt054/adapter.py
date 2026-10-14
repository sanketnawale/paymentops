"""camt.054.001.14 -> canonical AccountReportBundle adapter.

BankToCustomerDebitCreditNotificationV14. A camt.054 is an account-reporting notification,
NOT a payment instruction. It produces canonical ``AccountEntry`` records that are
reconciled against payment lifecycles. Multiple notifications and multiple entries are
supported.
"""

from __future__ import annotations

from lxml import etree

from iso_engine.account.entries import map_account, map_entry
from iso_engine.camt054.namespace import SupportedVersion
from iso_engine.common import child, child_text, children, parse_datetime
from payment_domain.models import (
    AccountReport,
    AccountReportBundle,
    AccountReportType,
)


def map_camt054_to_account_report(
    root: etree._Element, version: SupportedVersion
) -> AccountReportBundle:
    msg_root = child(root, "BkToCstmrDbtCdtNtfctn")
    grp = child(msg_root, "GrpHdr")
    reports: list[AccountReport] = []

    for ntfctn in children(msg_root, "Ntfctn"):
        path = "/BkToCstmrDbtCdtNtfctn/Ntfctn"
        account = map_account(child(ntfctn, "Acct"))
        entries = [map_entry(entry_el, f"{path}/Ntry") for entry_el in children(ntfctn, "Ntry")]
        reports.append(
            AccountReport(
                message_family="camt",
                message_definition=version.message_name,
                message_version=version.identifier,
                namespace=version.namespace,
                message_id=child_text(grp, "MsgId"),
                creation_datetime=parse_datetime(child_text(grp, "CreDtTm")),
                report_type=AccountReportType.NOTIFICATION,
                account=account,
                notification_id=child_text(ntfctn, "Id"),
                balances=[],
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
        report_type=AccountReportType.NOTIFICATION,
        reports=reports,
    )
