"""Analysis pipeline orchestrator.

Composes the deterministic vertical slice:

    secure parse -> identify -> XSD validate -> canonical map
    -> rules -> address analysis -> repair candidate -> revalidate
    -> structured AnalysisResult

The pipeline is pure/stateless; persistence and hashing are handled by the API service
layer. The XML/XSD validator is authoritative.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any
from uuid import uuid4

from address_engine.base import AddressProvider
from analysis.models import (
    AnalysisAddress,
    AnalysisDiff,
    AnalysisIssue,
    AnalysisResult,
    IsoAnalysisResult,
)
from iso_engine.common import IsoMessageMetadata
from iso_engine.lifecycle.correlation import (
    profile_from_message,
    profile_from_status_report,
)
from iso_engine.pacs008.adapter import map_pacs008_to_canonical
from iso_engine.pacs008.identifier import identify_pacs008
from iso_engine.registry import IsoMessageRegistry
from iso_engine.xml_security import SecureXmlDocument, secure_parse
from iso_engine.xsd_validator import SchemaValidationResult, validate_message, validate_pacs008
from payment_domain.models import (
    AccountReportBundle,
    AddressReadiness,
    LifecycleStatusReport,
    PaymentMessage,
    ValidationStatus,
)
from repair_engine.generator import addresses, generate_candidate
from repair_engine.models import RepairCandidate
from rules_engine.base import RuleEngine

ENGINE_VERSION = "0.3.0"


class AnalysisPipeline:
    def __init__(
        self,
        *,
        address_provider: AddressProvider,
        rules_engine: RuleEngine,
        max_payload_bytes: int = 1_048_576,
    ) -> None:
        self._address_provider = address_provider
        self._rules_engine = rules_engine
        self._max_payload_bytes = max_payload_bytes

    def analyze(
        self,
        payload: bytes,
        *,
        repair: bool = True,
        include_candidate_xml: bool = False,
    ) -> AnalysisResult:
        """Analyze a pacs.008 XML payload (existing entry point)."""
        doc = secure_parse(payload, max_bytes=self._max_payload_bytes)
        version = identify_pacs008(doc.root)
        xsd_result = validate_pacs008(doc.root, version)
        message = map_pacs008_to_canonical(doc.root, version)
        message.validation_status = (
            ValidationStatus.VALID if xsd_result.valid else ValidationStatus.INVALID
        )
        return self.analyze_message(
            message,
            doc=doc,
            xsd_result=xsd_result,
            message_type=version.identifier,
            message_version=version.identifier,
            repair=repair,
            include_candidate_xml=include_candidate_xml,
        )

    def analyze_iso(
        self,
        payload: bytes,
        registry: IsoMessageRegistry,
        *,
        max_transactions: int = 100,
    ) -> IsoAnalysisResult:
        """Analyze ANY supported ISO message via the registry.

        Dispatch is never family-only; the exact version is resolved from the namespace.
        Returns an ``IsoAnalysisResult``. Lifecycle correlation (DB-backed) is performed by the
        API service, which receives the correlation profiles carried here.
        """
        from iso_engine.common import build_metadata

        doc = secure_parse(payload, max_bytes=self._max_payload_bytes)
        reg_msg = registry.resolve_root(doc.root)
        definition = reg_msg.definition
        version_id = definition.version

        xsd_result = validate_message(doc.root, version_id)
        artifact = reg_msg.adapter(doc.root, reg_msg.version_obj)

        metadata = build_metadata(
            definition,
            message_id=getattr(artifact, "message_id", None),
            creation_datetime=getattr(artifact, "creation_datetime", None),
            source_adapter=f"{definition.message_family}_{version_id}",
            schema_version=version_id,
        )

        if isinstance(artifact, LifecycleStatusReport):
            return self._iso_status_result(artifact, metadata, xsd_result)
        if isinstance(artifact, PaymentMessage):
            return self._iso_payment_result(
                artifact, metadata, xsd_result, doc=doc, max_transactions=max_transactions
            )
        if isinstance(artifact, AccountReportBundle):
            return self._iso_account_result(
                artifact, metadata, xsd_result, max_entries=max_transactions
            )
        raise TypeError(f"adapter produced unsupported artifact type: {type(artifact)}")

    def _iso_account_result(
        self,
        bundle: AccountReportBundle,
        metadata: IsoMessageMetadata,
        xsd_result: SchemaValidationResult,
        *,
        max_entries: int,
    ) -> IsoAnalysisResult:
        if bundle.number_of_entries > max_entries:
            from iso_engine.xml_errors import PayloadTooLargeError

            raise PayloadTooLargeError(f"message exceeds {max_entries} account entries")
        # Address intelligence is NOT run for account reporting (Task 50/address rule).
        return IsoAnalysisResult(
            case_id=f"case-{uuid4().hex[:16]}",
            message_family=metadata.message_family,
            message_definition=metadata.message_definition,
            message_version=metadata.message_version,
            namespace=metadata.namespace,
            message_id=metadata.message_id,
            adapter_version=metadata.adapter_version,
            schema_validation=xsd_result.valid,
            schema_version=metadata.schema_version,
            original_validation_status="valid" if xsd_result.valid else "invalid",
            schema_issues=[
                AnalysisIssue(code=i.code, severity=i.severity, path=i.path, message=i.message)
                for i in xsd_result.issues
            ],
            canonical_model_version="payment_domain.v3",
            engine_version=ENGINE_VERSION,
            input_hash=_message_hash(bundle),
            account_report_type=bundle.report_type.value,
            account_reports=[r.model_dump(mode="json") for r in bundle.reports],
            account_entry_count=bundle.number_of_entries,
            warnings=[] if xsd_result.valid else ["Original message did not pass XSD validation"],
        )

    def _iso_payment_result(
        self,
        message: PaymentMessage,
        metadata: IsoMessageMetadata,
        xsd_result: SchemaValidationResult,
        *,
        doc: SecureXmlDocument,
        max_transactions: int,
    ) -> IsoAnalysisResult:
        if len(message.transactions) > max_transactions:
            from iso_engine.xml_errors import PayloadTooLargeError

            raise PayloadTooLargeError(f"message exceeds {max_transactions} transactions")
        message.validation_status = (
            ValidationStatus.VALID if xsd_result.valid else ValidationStatus.INVALID
        )
        result = self.analyze_message(
            message,
            doc=doc,
            xsd_result=xsd_result,
            message_type=metadata.message_version,
            message_version=metadata.message_version,
            repair=True,
            include_candidate_xml=False,
        )
        profiles = profile_from_message(message)
        return IsoAnalysisResult(
            case_id=result.case_id,
            message_family=metadata.message_family,
            message_definition=metadata.message_definition,
            message_version=metadata.message_version,
            namespace=metadata.namespace,
            message_id=metadata.message_id,
            adapter_version=metadata.adapter_version,
            schema_validation=xsd_result.valid,
            schema_version=metadata.schema_version,
            original_validation_status=result.original_validation_status,
            schema_issues=result.schema_issues,
            rule_findings=result.rule_findings,
            address_analyses=result.address_analyses,
            address_readiness=result.address_readiness,
            repair_status=result.repair_status,
            candidate_diff=result.candidate_diff,
            candidate_validation_status=result.candidate_validation_status,
            canonical_model_version="payment_domain.v2",
            engine_version=ENGINE_VERSION,
            input_hash=result.input_hash,
            warnings=result.warnings,
            correlation_profiles=[p.__dict__ for p in profiles],
        )

    def _iso_status_result(
        self,
        report: LifecycleStatusReport,
        metadata: IsoMessageMetadata,
        xsd_result: SchemaValidationResult,
    ) -> IsoAnalysisResult:
        profiles = profile_from_status_report(report)
        normalized = (
            report.transaction_statuses[0].normalized_status.value
            if report.transaction_statuses
            else report.group_status.value
        )
        raw = (
            report.transaction_statuses[0].raw_iso_status
            if report.transaction_statuses
            else report.group_status_raw
        )
        return IsoAnalysisResult(
            case_id=f"case-{uuid4().hex[:16]}",
            message_family=metadata.message_family,
            message_definition=metadata.message_definition,
            message_version=metadata.message_version,
            namespace=metadata.namespace,
            message_id=metadata.message_id,
            adapter_version=metadata.adapter_version,
            schema_validation=xsd_result.valid,
            schema_version=metadata.schema_version,
            original_validation_status="valid" if xsd_result.valid else "invalid",
            schema_issues=[
                AnalysisIssue(code=i.code, severity=i.severity, path=i.path, message=i.message)
                for i in xsd_result.issues
            ],
            canonical_model_version="payment_domain.v2",
            engine_version=ENGINE_VERSION,
            input_hash=_message_hash(report),
            raw_status=raw,
            normalized_status=normalized,
            correlation_profiles=[p.__dict__ for p in profiles],
            warnings=[] if xsd_result.valid else ["Original message did not pass XSD validation"],
        )

    def analyze_message(
        self,
        message: PaymentMessage,
        *,
        doc: SecureXmlDocument | None = None,
        xsd_result: SchemaValidationResult | None = None,
        message_type: str | None = None,
        message_version: str | None = None,
        repair: bool = True,
        include_candidate_xml: bool = False,
    ) -> AnalysisResult:
        """Run the deterministic engine on an already-mapped canonical ``PaymentMessage``.

        Used by the mapping engine for JSON/CSV/custom-XML inputs. ``doc``/``xsd_result`` are
        provided when the source is ISO XML (pacs.008) so XML reconstruction + XSD revalidation
        can run; otherwise the candidate is re-validated against the rules on the model.
        """
        case_id = f"case-{uuid4().hex[:16]}"
        xsd_valid = xsd_result.valid if xsd_result else True

        findings = self._rules_engine.evaluate(message)

        address_analyses: list[AnalysisAddress] = []
        overall_readiness: list[AddressReadiness] = []
        any_fallback = False
        provider_used: str | None = None
        provider_version_used: str | None = None
        for tx in message.transactions:
            for label, addr in addresses(tx):
                analysis = self._address_provider.analyze(addr)
                overall_readiness.append(analysis.readiness)
                if analysis.fallback:
                    any_fallback = True
                if analysis.available:
                    provider_used = analysis.provider
                    provider_version_used = analysis.provider_version
                address_analyses.append(
                    AnalysisAddress(
                        party=label,
                        readiness=analysis.readiness.value,
                        evidence_level=analysis.evidence_level.value,
                        country_code=analysis.country_code,
                        town_name=analysis.town_name,
                        provider=analysis.provider,
                        provider_version=analysis.provider_version,
                        note=analysis.note,
                        fallback=analysis.fallback,
                    )
                )

        candidate: RepairCandidate | None = None
        if repair:
            candidate = generate_candidate(
                message,
                doc,
                address_provider=self._address_provider,
                rules_engine=self._rules_engine,
            )

        input_hash = _message_hash(message)
        output_hash = (
            sha256(candidate.xml.encode("utf-8")).hexdigest()
            if candidate and candidate.xml
            else None
        )

        return AnalysisResult(
            case_id=case_id,
            message_type=message_type or message.message_type,
            message_version=message_version,
            original_validation_status="valid" if xsd_valid else "invalid",
            schema_issues=[
                AnalysisIssue(code=i.code, severity=i.severity, path=i.path, message=i.message)
                for i in (xsd_result.issues if xsd_result else [])
            ],
            rule_findings=[f.to_dict() for f in findings],
            address_analyses=address_analyses,
            address_readiness=_aggregate_readiness(overall_readiness),
            repair_status=candidate.status.value if candidate else None,
            candidate_diff=[
                AnalysisDiff(
                    path=c.path,
                    before=c.before,
                    after=c.after,
                    source=c.source.value,
                    status=c.status.value,
                )
                for c in (candidate.changes if candidate else [])
            ],
            candidate_validation_status=candidate.status.value if candidate else None,
            candidate_xml=candidate.xml
            if (include_candidate_xml and candidate and candidate.xml)
            else None,
            ruleset_version=self._rules_engine.version,
            address_provider=provider_used,
            address_provider_version=provider_version_used,
            address_provider_fallback=any_fallback,
            input_hash=input_hash,
            output_hash=output_hash,
            warnings=_warnings(xsd_valid, candidate, any_fallback),
        )


def _message_hash(message: Any) -> str:
    """Deterministic hash of a canonical model (used when no raw payload is hashed)."""
    return sha256(message.model_dump_json(exclude_none=True).encode("utf-8")).hexdigest()


def _aggregate_readiness(levels: list[AddressReadiness]) -> str:
    if not levels:
        return "UNRESOLVED"
    if all(x == AddressReadiness.READY for x in levels):
        return "READY"
    if AddressReadiness.UNRESOLVED in levels:
        return "UNRESOLVED"
    if AddressReadiness.REVIEW_REQUIRED in levels:
        return "REVIEW_REQUIRED"
    return "REPAIRABLE"


def _warnings(
    xsd_valid: bool, candidate: RepairCandidate | None, any_fallback: bool = False
) -> list[str]:
    warnings: list[str] = []
    if not xsd_valid:
        warnings.append("Original message did not pass XSD validation")
    if candidate and candidate.status.value == "REVIEW_REQUIRED":
        warnings.append("Repair candidate requires human review")
    if any_fallback:
        warnings.append("ADDRESS_PROVIDER_FALLBACK")
    return warnings
