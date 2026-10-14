"""Unit tests for the rules engine."""

from __future__ import annotations

from rules_engine import RULESET_VERSION, build_address_ruleset
from rules_engine.base import Severity


def _findings_for(fixture_name: str) -> list[dict]:
    from tests.conftest import load_fixture

    from iso_engine.pacs008.adapter import map_pacs008_to_canonical
    from iso_engine.pacs008.identifier import identify_pacs008
    from iso_engine.xml_security import secure_parse

    doc = secure_parse(load_fixture(fixture_name))
    version = identify_pacs008(doc.root)
    msg = map_pacs008_to_canonical(doc.root, version)
    engine = build_address_ruleset()
    return [f.to_dict() for f in engine.evaluate(msg)]


def test_ruleset_version_is_stable():
    assert RULESET_VERSION == "cloudnova-address-v1"


def test_valid_message_no_findings():
    assert _findings_for("valid_structured") == []


def test_missing_town_fires_adr_001():
    findings = _findings_for("missing_town")
    assert any(f["rule_id"] == "ADR-001" for f in findings)


def test_missing_country_fires_adr_002():
    findings = _findings_for("missing_country")
    assert any(f["rule_id"] == "ADR-002" for f in findings)


def test_country_full_name_fires_adr_003():
    findings = _findings_for("country_full_name")
    assert any(f["rule_id"] == "ADR-003" for f in findings)


def test_adrline_only_fires_adr_004():
    findings = _findings_for("address_adrline_only")
    assert any(f["rule_id"] == "ADR-004" for f in findings)


def test_hybrid_fires_adr_005():
    findings = _findings_for("hybrid_address")
    assert any(f["rule_id"] == "ADR-005" for f in findings)


def test_structural_rule_missing_amount():
    from payment_domain.models import PaymentMessage, PaymentTransaction
    from rules_engine.base import RuleEngine
    from rules_engine.rules.structural_rules import MissingAmountRule

    engine = RuleEngine([MissingAmountRule()])
    msg = PaymentMessage(transactions=[PaymentTransaction()])
    findings = engine.evaluate(msg)
    assert any(f.rule_id == "ISO-002" and f.severity == Severity.ERROR for f in findings)
