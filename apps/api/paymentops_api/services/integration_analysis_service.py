"""Profile-resolved analysis service.

Authenticates a client -> resolves organization -> resolves published profile -> validates
accepted input format -> applies mapping -> builds canonical PaymentMessage -> runs the
PaymentOps engine with profile rules -> returns result + version metadata + geography
coverage.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from typing import cast

from paymentops_api.settings import Settings

from address_engine.base import AddressProvider
from address_engine.providers import (
    CloudNovaAddressProvider,
    FallbackAddressProvider,
    SwiftDerivedAddressProvider,
)
from analysis.pipeline import AnalysisPipeline
from integration_profiles.models import InputFormat, IntegrationProfile
from iso_engine.registry import IsoMessageRegistry, build_default_registry
from iso_engine.xml_security import SecureXmlDocument, secure_parse
from iso_engine.xsd_validator import SchemaValidationResult, validate_message
from mapping_engine.mapper import map_to_canonical
from payment_domain.models import PaymentMessage
from rules_engine import build_address_ruleset
from rules_engine.declarative import CompositeRuleEngine, build_declarative_rules

# Development address coverage (8 countries).
DEV_COVERAGE = {"IT", "IN", "SA", "GB", "DE", "FR", "ES", "NL"}


def build_profile_rules(profile: IntegrationProfile) -> CompositeRuleEngine:
    baseline = build_address_ruleset()._rules
    customer_rules = build_declarative_rules(profile.rules)
    return CompositeRuleEngine(baseline, org_rules=customer_rules)


def build_profile_provider(address_policy: str, settings: Settings) -> AddressProvider:
    use_swift = address_policy == "swift" or (
        address_policy == "auto" and bool(settings.swift_address_url)
    )
    if use_swift:
        swift = SwiftDerivedAddressProvider(
            settings.swift_address_url,
            timeout_seconds=settings.swift_address_timeout,
            max_retries=settings.swift_address_max_retries,
        )
        return FallbackAddressProvider(swift, CloudNovaAddressProvider())
    return CloudNovaAddressProvider()


def map_input(
    profile: IntegrationProfile, payload: bytes, registry: IsoMessageRegistry
) -> tuple[PaymentMessage, dict[str, object]]:
    """Map raw input (by profile.input_format) into a canonical PaymentMessage."""
    fmt = profile.input_format
    if fmt == InputFormat.ISO20022_XML:
        doc = secure_parse(payload)
        reg_msg = registry.resolve_root(doc.root)
        version_id = reg_msg.definition.version
        if profile.allowed_messages and version_id not in profile.allowed_messages:
            raise ValueError(f"message {version_id} not allowed for this profile")
        xsd = validate_message(doc.root, version_id)
        artifact = reg_msg.adapter(doc.root, reg_msg.version_obj)
        if not isinstance(artifact, PaymentMessage):
            raise ValueError("profile analysis supports payment messages only")
        return artifact, {"xsd_result": xsd, "doc": doc, "message_version": version_id}

    if fmt == InputFormat.JSON:
        data = json.loads(payload.decode("utf-8"))
        result = map_to_canonical(profile.mapping, data)
        return result.message, {
            "mapping_result": result,
            "message_version": profile.mapping_version,
        }

    if fmt == InputFormat.CSV:
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8")))
        rows = list(reader)
        result = map_to_canonical(profile.mapping, rows)
        return result.message, {
            "mapping_result": result,
            "message_version": profile.mapping_version,
        }

    if fmt == InputFormat.CUSTOM_XML:
        doc = secure_parse(payload)
        result = map_to_canonical(profile.mapping, doc.root)
        return result.message, {
            "mapping_result": result,
            "message_version": profile.mapping_version,
        }

    raise ValueError("unsupported input format")


def compute_coverage(message: PaymentMessage) -> str:
    """Return SUPPORTED / UNSUPPORTED_GEOGRAPHY / UNKNOWN based on addresses."""
    countries = set()
    for tx in message.transactions:
        for party in (tx.debtor, tx.creditor):
            if party and party.postal_address and party.postal_address.country:
                countries.add(party.postal_address.country.upper())
        for agent in (tx.debtor_agent, tx.creditor_agent):
            if agent and agent.postal_address and agent.postal_address.country:
                countries.add(agent.postal_address.country.upper())
    if not countries:
        return "UNKNOWN"
    return "SUPPORTED" if countries <= DEV_COVERAGE else "UNSUPPORTED_GEOGRAPHY"


def analyze_profile(
    profile: IntegrationProfile,
    payload: bytes,
    *,
    settings: Settings,
    registry: IsoMessageRegistry | None = None,
    repair: bool = True,
    include_candidate_xml: bool = False,
) -> dict[str, object]:
    registry = registry or build_default_registry()
    message, meta = map_input(profile, payload, registry)
    rules = build_profile_rules(profile)
    provider = build_profile_provider(profile.address_policy, settings)
    pipeline = AnalysisPipeline(address_provider=provider, rules_engine=rules)

    result = pipeline.analyze_message(
        message,
        doc=cast("SecureXmlDocument | None", meta.get("doc")),
        xsd_result=cast("SchemaValidationResult | None", meta.get("xsd_result")),
        message_type=profile.input_format.value,
        message_version=cast("str | None", meta.get("message_version")) or profile.mapping_version,
        repair=repair,
        include_candidate_xml=include_candidate_xml,
    )
    coverage = compute_coverage(message)
    result.address_provider_coverage = coverage
    return {
        "case_id": result.case_id,
        "integration_profile_version": str(profile.version_number),
        "mapping_version": profile.mapping_version,
        "ruleset_version": profile.ruleset_version,
        "engine_version": "0.1.0",
        "address_provider": result.address_provider,
        "address_provider_version": result.address_provider_version,
        "address_provider_fallback": result.address_provider_fallback,
        "address_provider_coverage": coverage,
        "original_validation_status": result.original_validation_status,
        "address_readiness": result.address_readiness,
        "repair_status": result.repair_status,
        "candidate_validation_status": result.candidate_validation_status,
        "candidate_diff": [d.model_dump() for d in result.candidate_diff],
        "rule_findings": result.rule_findings,
        "address_analyses": [a.model_dump() for a in result.address_analyses],
        "input_hash": result.input_hash,
        "output_hash": result.output_hash,
        "warnings": result.warnings,
        "processed_at": datetime.now(UTC).isoformat(),
    }
