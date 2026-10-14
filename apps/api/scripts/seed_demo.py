# ruff: noqa: E501  (long lines are inline XML payload literals)
"""Seed the CloudNova Demo Bank tenant with synthetic demo scenarios.

Idempotent: re-running does not duplicate messages (deduplicated by payload hash). Uses only
synthetic data. Run inside the API container:

    python -m scripts.seed_demo
    python -m scripts.seed_demo --org cloudnova-demo-bank
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from paymentops_api.db.base import Database
from paymentops_api.db.models import Organization
from paymentops_api.services import iso_analysis_service
from paymentops_api.settings import get_settings
from sqlalchemy import select

from address_engine.providers import CloudNovaAddressProvider
from analysis.pipeline import AnalysisPipeline
from iso_engine import build_default_registry
from rules_engine import build_address_ruleset

# --- Synthetic demo payloads (no real customer data) ---

PAIN001 = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.13">
  <CstmrCdtTrfInitn>
    <GrpHdr><MsgId>DEMO-PAIN-0001</MsgId><CreDtTm>2026-01-10T09:30:00+00:00</CreDtTm><NbOfTxs>1</NbOfTxs></GrpHdr>
    <PmtInf>
      <PmtInfId>DEMO-PMTINF-0001</PmtInfId><PmtMtd>TRF</PmtMtd><BtchBookg>false</BtchBookg>
      <ReqdExctnDt>2026-01-12</ReqdExctnDt>
      <Dbtr><Nm>CloudNova Demo Corporation</Nm><PstlAdr><TwnNm>Milano</TwnNm><Ctry>IT</Ctry></PstlAdr></Dbtr>
      <DbtrAcct><Id><IBAN>IT60X0542811101000000123456</IBAN></Id></DbtrAcct>
      <DbtrAgt><FinInstnId><BICFI>ITBIC12345</BICFI></FinInstnId></DbtrAgt>
      <CdtTrfTxInf>
        <PmtId><InstrId>DEMO-INSTR-0001</InstrId><EndToEndId>DEMO-E2E-0001</EndToEndId><TxId>DEMO-TX-0001</TxId></PmtId>
        <Amt><InstdAmt Ccy="EUR">12500.00</InstdAmt></Amt>
        <CdtrAgt><FinInstnId><BICFI>DEBIC54321</BICFI></FinInstnId></CdtrAgt>
        <Cdtr><Nm>Demo Industria SPA</Nm><PstlAdr><TwnNm>Berlin</TwnNm><Ctry>DE</Ctry></PstlAdr></Cdtr>
        <CdtrAcct><Id><IBAN>DE89370400440532013000</IBAN></Id></CdtrAcct>
        <RmtInf><Ustrd>Invoice INV-92881</Ustrd></RmtInf>
      </CdtTrfTxInf>
    </PmtInf>
  </CstmrCdtTrfInitn>
</Document>"""

PACS008 = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
  <FIToFICstmrCdtTrf>
    <GrpHdr><MsgId>DEMO-PACS008-0001</MsgId><CreDtTm>2026-01-11T09:00:00+00:00</CreDtTm><NbOfTxs>1</NbOfTxs><SttlmInf><SttlmMtd>INDA</SttlmMtd></SttlmInf></GrpHdr>
    <CdtTrfTxInf>
      <PmtId><InstrId>DEMO-INSTR-0001</InstrId><EndToEndId>DEMO-E2E-0001</EndToEndId><TxId>DEMO-TX-0001</TxId></PmtId>
      <Amt><InstdAmt Ccy="EUR">12500.00</InstdAmt></Amt>
      <Dbtr><Nm>CloudNova Demo Corporation</Nm><PstlAdr><TwnNm>Milano</TwnNm><Ctry>IT</Ctry></PstlAdr></Dbtr>
      <DbtrAcct><Id><IBAN>IT60X0542811101000000123456</IBAN></Id></DbtrAcct>
      <DbtrAgt><FinInstnId><BICFI>ITBIC12345</BICFI></FinInstnId></DbtrAgt>
      <CdtrAgt><FinInstnId><BICFI>DEBIC54321</BICFI></FinInstnId></CdtrAgt>
      <Cdtr><Nm>Demo Industria SPA</Nm><PstlAdr><TwnNm>Berlin</TwnNm><Ctry>DE</Ctry></PstlAdr></Cdtr>
      <CdtrAcct><Id><IBAN>DE89370400440532013000</IBAN></Id></CdtrAcct>
      <RmtInf><Ustrd>Invoice INV-92881</Ustrd></RmtInf>
    </CdtTrfTxInf>
  </FIToFICstmrCdtTrf>
</Document>"""

PACS008_REPAIR = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
  <FIToFICstmrCdtTrf>
    <GrpHdr><MsgId>DEMO-PACS008-REPAIR</MsgId><CreDtTm>2026-01-11T09:05:00+00:00</CreDtTm><NbOfTxs>1</NbOfTxs></GrpHdr>
    <CdtTrfTxInf>
      <PmtId><InstrId>DEMO-INSTR-R</InstrId><EndToEndId>DEMO-E2E-R</EndToEndId></PmtId>
      <Amt><InstdAmt Ccy="EUR">980.00</InstdAmt></Amt>
      <Dbtr><Nm>Demo Corporation</Nm><PstlAdr><TwnNm>milano</TwnNm><Ctry>IT</Ctry></PstlAdr></Dbtr>
      <DbtrAcct><Id><IBAN>IT60X0542811101000000123456</IBAN></Id></DbtrAcct>
      <CdtrAgt><FinInstnId><BICFI>DEBIC54321</BICFI></FinInstnId></CdtrAgt>
      <Cdtr><Nm>Demo Logistica SRL</Nm><PstlAdr><TwnNm>roma</TwnNm><Ctry>IT</Ctry></PstlAdr></Cdtr>
      <CdtrAcct><Id><IBAN>IT60X0542811101000000654321</IBAN></Id></CdtrAcct>
      <RmtInf><Ustrd>Invoice INV-55001</Ustrd></RmtInf>
    </CdtTrfTxInf>
  </FIToFICstmrCdtTrf>
</Document>"""

PACS002 = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.002.001.16">
  <FIToFIPmtStsRpt>
    <GrpHdr><MsgId>DEMO-STS-0001</MsgId><CreDtTm>2026-01-12T08:00:00+00:00</CreDtTm></GrpHdr>
    <OrgnlGrpInfAndSts><OrgnlMsgId>DEMO-PAIN-0001</OrgnlMsgId><OrgnlMsgNmId>pain.001.001.13</OrgnlMsgNmId><GrpSts>ACCP</GrpSts></OrgnlGrpInfAndSts>
    <TxInfAndSts>
      <OrgnlInstrId>DEMO-INSTR-0001</OrgnlInstrId><OrgnlEndToEndId>DEMO-E2E-0001</OrgnlEndToEndId><OrgnlTxId>DEMO-TX-0001</OrgnlTxId><TxSts>ACCP</TxSts>
      <OrgnlTxRef><PmtId><InstrId>DEMO-INSTR-0001</InstrId><EndToEndId>DEMO-E2E-0001</EndToEndId><TxId>DEMO-TX-0001</TxId></PmtId><Amt><InstdAmt Ccy="EUR">12500.00</InstdAmt></Amt></OrgnlTxRef>
    </TxInfAndSts>
  </FIToFIPmtStsRpt>
</Document>"""

CAMT054 = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.054.001.14">
  <BkToCstmrDbtCdtNtfctn>
    <GrpHdr><MsgId>DEMO-CAMT054-0001</MsgId><CreDtTm>2026-01-12T10:00:00+00:00</CreDtTm></GrpHdr>
    <Ntfctn><Id>DEMO-NTFCTN-0001</Id>
      <Acct><Id><IBAN>IT60X0542811101000000123456</IBAN></Id><Ccy>EUR</Ccy><Svcr><FinInstnId><BICFI>ITBIC12345</BICFI></FinInstnId></Svcr></Acct>
      <Ntry>
        <NtryRef>DEMO-NTRY-0001</NtryRef><Amt Ccy="EUR">12500.00</Amt><CdtDbtInd>DBIT</CdtDbtInd><Sts><Cd>BOOK</Cd></Sts>
        <BookgDt><Dt>2026-01-12</Dt></BookgDt><ValDt><Dt>2026-01-12</Dt></ValDt><AcctSvcrRef>DEMO-ASR-0001</AcctSvcrRef>
        <BkTxCd><Domn><Cd>PMNT</Cd><Fmly><Cd>ICDT</Cd><SubFmlyCd>ESCT</SubFmlyCd></Fmly></Domn></BkTxCd>
        <NtryDtls><TxDtls><Refs><InstrId>DEMO-INSTR-0001</InstrId><EndToEndId>DEMO-E2E-0001</EndToEndId><TxId>DEMO-TX-0001</TxId></Refs><Amt Ccy="EUR">12500.00</Amt><RmtInf><Ustrd>Invoice INV-92881</Ustrd></RmtInf></TxDtls></NtryDtls>
      </Ntry>
    </Ntfctn>
  </BkToCstmrDbtCdtNtfctn>
</Document>"""

CAMT053 = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.14">
  <BkToCstmrStmt>
    <GrpHdr><MsgId>DEMO-CAMT053-0001</MsgId><CreDtTm>2026-01-13T00:05:00+00:00</CreDtTm></GrpHdr>
    <Stmt><Id>DEMO-STMT-0001</Id><ElctrncSeqNb>1</ElctrncSeqNb>
      <Acct><Id><IBAN>IT60X0542811101000000123456</IBAN></Id><Ccy>EUR</Ccy><Svcr><FinInstnId><BICFI>ITBIC12345</BICFI></FinInstnId></Svcr></Acct>
      <FrToDt><FrDtTm>2026-01-12T00:00:00+00:00</FrDtTm><ToDtTm>2026-01-12T23:59:59+00:00</ToDtTm></FrToDt>
      <Bal><Tp><CdOrPrtry><Cd>OPBD</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">100000.00</Amt><CdtDbtInd>CRDT</CdtDbtInd></Bal>
      <Bal><Tp><CdOrPrtry><Cd>CLBD</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">87500.00</Amt><CdtDbtInd>CRDT</CdtDbtInd></Bal>
      <Ntry>
        <NtryRef>DEMO-NTRY-0001</NtryRef><Amt Ccy="EUR">12500.00</Amt><CdtDbtInd>DBIT</CdtDbtInd><Sts><Cd>BOOK</Cd></Sts>
        <BookgDt><Dt>2026-01-12</Dt></BookgDt><ValDt><Dt>2026-01-12</Dt></ValDt><AcctSvcrRef>DEMO-ASR-0001</AcctSvcrRef>
        <BkTxCd><Domn><Cd>PMNT</Cd><Fmly><Cd>ICDT</Cd><SubFmlyCd>ESCT</SubFmlyCd></Fmly></Domn></BkTxCd>
        <NtryDtls><TxDtls><Refs><InstrId>DEMO-INSTR-0001</InstrId><EndToEndId>DEMO-E2E-0001</EndToEndId><TxId>DEMO-TX-0001</TxId></Refs><Amt Ccy="EUR">12500.00</Amt><RmtInf><Ustrd>Invoice INV-92881</Ustrd></RmtInf></TxDtls></NtryDtls>
      </Ntry>
    </Stmt>
  </BkToCstmrStmt>
</Document>"""

PAYLOADS = [PAIN001, PACS008, PACS008_REPAIR, PACS002, CAMT054, CAMT053]


async def _seed(org_public_id: str) -> int:
    db = Database(get_settings())
    pipeline = AnalysisPipeline(
        address_provider=CloudNovaAddressProvider(), rules_engine=build_address_ruleset()
    )
    registry = build_default_registry()
    try:
        async for session in db.session():
            result = await session.execute(
                select(Organization).where(Organization.public_id == org_public_id)
            )
            org = result.scalar_one_or_none()
            if org is None:
                print(f"Organization '{org_public_id}' not found.")
                return 1
            for payload in PAYLOADS:
                analysis = await iso_analysis_service.analyze_iso_message(
                    session,
                    str(org.id),
                    payload.encode("utf-8"),
                    registry=registry,
                    pipeline=pipeline,
                )
                print(f"  seeded {analysis.message_version} -> {analysis.correlation_status}")
            print(f"Demo seed complete for '{org_public_id}'.")
            return 0
    finally:
        await db.dispose()
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="seed_demo")
    parser.add_argument("--org", default="cloudnova-demo-bank")
    args = parser.parse_args()
    sys.exit(asyncio.run(_seed(args.org)))
