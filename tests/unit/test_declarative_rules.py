"""Unit tests for the transform library and declarative rules."""

from __future__ import annotations

from mapping_engine.transforms import supported_transforms, transform
from payment_domain.models import Party, PaymentMessage, PaymentTransaction, PostalAddress
from rules_engine import RuleConfig, build_declarative_rules, validate_rule_config
from rules_engine.declarative import CompositeRuleEngine, resolve_field


def test_transforms_deterministic_and_safe():
    assert transform("trim", "  x  ") == "x"
    assert transform("upper", "abc") == "ABC"
    assert transform("collapse_whitespace", "a  b") == "a b"
    assert transform("country_to_iso2", "Italy") == "IT"
    assert transform("parse_decimal", "100.00") is not None
    assert transform("parse_decimal", "not-a-number") == "not-a-number"  # fails safely
    assert transform("unsupported_op", "x") == "x"
    assert "eval(" not in supported_transforms()


def test_rule_config_validation():
    good = RuleConfig(
        rule_id="CUSTOM-001", field="creditor.postal_address.country", operator="in", value=["IT"]
    )
    assert validate_rule_config(good) == []
    bad = RuleConfig(rule_id="CUSTOM-002", field="x", operator="eval", value="1")
    assert any("unsupported operator" in e for e in validate_rule_config(bad))
    system = RuleConfig(
        rule_id="CUSTOM-003",
        field="x",
        operator="equals",
        value=1,
        classification="SYSTEM_MANDATORY",
    )
    assert any("SYSTEM_MANDATORY" in e for e in validate_rule_config(system))


def test_declarative_rule_fires_only_for_matching_tenant_data():
    config = RuleConfig(
        rule_id="CUSTOM-001",
        field="creditor.postal_address.country",
        operator="in",
        value=["IT", "DE"],
        severity="WARNING",
    )
    engine = CompositeRuleEngine([], org_rules=build_declarative_rules([config]))

    msg_it = PaymentMessage(
        transactions=[
            PaymentTransaction(creditor=Party(postal_address=PostalAddress(country="IT")))
        ]
    )
    findings = engine.evaluate(msg_it)
    assert any(f.rule_id == "CUSTOM-001" for f in findings)

    msg_us = PaymentMessage(
        transactions=[
            PaymentTransaction(creditor=Party(postal_address=PostalAddress(country="US")))
        ]
    )
    assert all(f.rule_id != "CUSTOM-001" for f in engine.evaluate(msg_us))


def test_resolve_field_path():
    tx = PaymentTransaction(creditor=Party(postal_address=PostalAddress(country="IT")))
    assert resolve_field(tx, "creditor.postal_address.country") == "IT"
    assert resolve_field(tx, "creditor.postal_address.town_name") is None
