"""Repair candidate generation (Task 12).

Flow:
    original -> analysis -> proposed field changes -> reconstruct candidate XML
             -> XSD validation -> CloudNova rule validation
             -> VALIDATED_CANDIDATE (only if schema + rules pass)

We never present a candidate as a "corrected payment" until deterministic validation succeeds.
"""

from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from address_engine.base import AddressProvider
from iso_engine.pacs008.identifier import identify_pacs008
from iso_engine.xml_security import SecureXmlDocument
from iso_engine.xsd_validator import validate_pacs008
from payment_domain.models import (
    CandidateStatus,
    PaymentMessage,
    PaymentTransaction,
    PostalAddress,
    SourceFormat,
)
from repair_engine.models import ChangeSource, DiffEntry, RepairCandidate
from repair_engine.xml_reconstruction import apply_changes, serialize
from rules_engine.base import RuleEngine, RuleFinding


def addresses(transaction: PaymentTransaction) -> list[tuple[str, PostalAddress]]:
    pairs: list[tuple[str, PostalAddress]] = []
    for label, party in (("Dbtr", transaction.debtor), ("Cdtr", transaction.creditor)):
        if party and party.postal_address:
            pairs.append((label, party.postal_address))
    for label, agent in (
        ("DbtrAgt", transaction.debtor_agent),
        ("CdtrAgt", transaction.creditor_agent),
    ):
        if agent and agent.postal_address:
            pairs.append((label, agent.postal_address))
    return pairs


def generate_candidate(
    message: PaymentMessage,
    doc: SecureXmlDocument | None,
    *,
    address_provider: AddressProvider,
    rules_engine: RuleEngine,
) -> RepairCandidate:
    """Generate, reconstruct, and deterministically re-validate a repair candidate.

    ``doc`` is the secure XML tree for XML sources (pacs.008). For non-XML sources (mapped
    JSON/CSV/custom XML) ``doc`` is ``None``; the candidate is re-validated against the rules
    on the canonical model instead of the XML/XSD.
    """

    changes: list[DiffEntry] = []
    for tx in message.transactions:
        for _label, addr in addresses(tx):
            if not addr.source_path:
                continue
            analysis = address_provider.analyze(addr)
            base = addr.source_path
            raw_country = addr.original_fields.get("Ctry") or addr.country
            raw_town = addr.original_fields.get("TwnNm") or addr.town_name
            if analysis.country_code and raw_country != analysis.country_code:
                changes.append(
                    DiffEntry(
                        path=f"{base}/Ctry",
                        before=raw_country,
                        after=analysis.country_code,
                        source=ChangeSource.ADDRESS_PROVIDER,
                    )
                )
            if analysis.town_name and raw_town != analysis.town_name:
                changes.append(
                    DiffEntry(
                        path=f"{base}/TwnNm",
                        before=raw_town,
                        after=analysis.town_name,
                        source=ChangeSource.ADDRESS_PROVIDER,
                    )
                )

    candidate_id = f"RC-{uuid4().hex[:12]}"

    if not changes:
        return RepairCandidate(
            candidate_id=candidate_id,
            changes=[],
            xml=None,
            status=CandidateStatus.VALIDATED,
            note="No repair changes required",
        )

    if doc is not None and message.source_format == SourceFormat.XML_PACS_008:
        # Reconstruct the candidate XML from the original tree (never mutating the original).
        new_root, applied = apply_changes(doc.root, changes)
        candidate_xml = serialize(new_root)
        version = identify_pacs008(new_root)
        xsd_result = validate_pacs008(new_root, version)
        from iso_engine.pacs008.adapter import map_pacs008_to_canonical

        candidate_message = map_pacs008_to_canonical(new_root, version)
        candidate_findings = rules_engine.evaluate(candidate_message)
        if xsd_result.valid and not _blocking_findings(candidate_findings):
            status = CandidateStatus.VALIDATED
        else:
            status = CandidateStatus.REVIEW_REQUIRED
        return RepairCandidate(
            candidate_id=candidate_id,
            changes=applied,
            xml=candidate_xml,
            status=status,
            xsd_result=xsd_result,
            rule_findings=candidate_findings,
        )

    # Non-XML source: apply the address changes to the canonical model and re-run rules.
    candidate_message = _apply_to_message(message, changes)
    candidate_findings = rules_engine.evaluate(candidate_message)
    if _blocking_findings(candidate_findings):
        status = CandidateStatus.REVIEW_REQUIRED
    else:
        status = CandidateStatus.VALIDATED
    return RepairCandidate(
        candidate_id=candidate_id,
        changes=changes,
        xml=None,
        status=status,
        rule_findings=candidate_findings,
    )


def _apply_to_message(message: PaymentMessage, changes: list[DiffEntry]) -> PaymentMessage:
    """Apply address-field changes to a deep copy of the canonical message (no XML)."""
    updated = deepcopy(message)
    for change in changes:
        segments = [s for s in change.path.split("/") if s]
        if len(segments) < 4:
            continue
        try:
            tx_index = int(segments[1].strip("[]"))
        except ValueError:
            continue
        tx = updated.transactions[tx_index]
        party_name = segments[2]
        addr = None
        if party_name == "Cdtr" and tx.creditor and tx.creditor.postal_address:
            addr = tx.creditor.postal_address
        elif party_name == "Dbtr" and tx.debtor and tx.debtor.postal_address:
            addr = tx.debtor.postal_address
        if addr is None:
            continue
        field = segments[-1]
        if field == "Ctry" and change.after:
            addr.country = change.after
        elif field == "TwnNm" and change.after:
            addr.town_name = change.after
    return updated


def _blocking_findings(findings: list[RuleFinding]) -> bool:
    from rules_engine.base import Severity

    return any(f.severity in (Severity.ERROR, Severity.CRITICAL) for f in findings)
