# ISO 20022 Version Support Matrix

## Supported (implemented)

| Family | Definition | Version | Analyze | Canonical Mapping | Lifecycle | Address | Matching |
|--------|-----------|---------|---------|-------------------|-----------|---------|----------|
| pacs.008 | pacs.008.001.08 | supported | ✅ | ✅ (PaymentMessage) | ✅ | ✅ | ✅ |
| pain.001 | pain.001.001.13 | supported | ✅ | ✅ (PaymentMessage) | ✅ | ✅ | ✅ |
| pacs.002 | pacs.002.001.16 | supported | ✅ | ✅ (LifecycleStatusReport) | ✅ | — (status only) | ✅ |
| pacs.009 | pacs.009.001.13 | supported | ✅ | ✅ (PaymentMessage) | ✅ | ✅ | ✅ |
| camt.053 | camt.053.001.14 | supported | ✅ | ✅ (AccountReport/AccountEntry) | ✅ | — (account reporting) | ✅ |
| camt.054 | camt.054.001.14 | supported | ✅ | ✅ (AccountReport/AccountEntry) | ✅ | — (account reporting) | ✅ |

Legend:
- ✅ = supported
- — = not applicable (pacs.002 is a status report; camt messages are account reporting)
- PLANNED = not implemented, roadmap only

## Planned (not implemented)

| Family | Definition | Version | Status |
|--------|-----------|---------|--------|
| camt.052 | — | — | PLANNED (out of Week 6 scope) |
| camt.056 | — | — | PLANNED (out of Week 6 scope) |

## Machine-readable

```json
{
  "supported": [
    {"family": "pacs", "definition": "FIToFICustomerCreditTransferV08", "version": "pacs.008.001.08", "root_element": "FIToFICstmrCdtTrf"},
    {"family": "pain", "definition": "CustomerCreditTransferInitiationV13", "version": "pain.001.001.13", "root_element": "CstmrCdtTrfInitn"},
    {"family": "pacs", "definition": "FIToFIPaymentStatusReportV16", "version": "pacs.002.001.16", "root_element": "FIToFIPmtStsRpt"},
    {"family": "pacs", "definition": "FinancialInstitutionCreditTransferV13", "version": "pacs.009.001.13", "root_element": "FICdtTrf"},
    {"family": "camt", "definition": "BankToCustomerStatementV14", "version": "camt.053.001.14", "root_element": "Stmt"},
    {"family": "camt", "definition": "BankToCustomerDebitCreditNotificationV14", "version": "camt.054.001.14", "root_element": "Ntfctn"}
  ],
  "planned": ["camt.052", "camt.056"]
}
```

Do not claim the planned messages are supported.
