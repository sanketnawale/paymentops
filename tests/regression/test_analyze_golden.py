"""Regression / golden tests.

Guards against unintended changes to the deterministic analysis behaviour. These assert
stable, high-level outcomes for the synthetic fixtures.
"""

from __future__ import annotations

import pytest
from tests.conftest import load_fixture

from address_engine.providers import CloudNovaAddressProvider
from analysis import AnalysisPipeline
from rules_engine import build_address_ruleset


@pytest.fixture(scope="module")
def pipeline() -> AnalysisPipeline:
    return AnalysisPipeline(
        address_provider=CloudNovaAddressProvider(),
        rules_engine=build_address_ruleset(),
    )


@pytest.mark.parametrize(
    ("fixture", "validation", "readiness"),
    [
        ("valid_structured", "valid", "READY"),
        ("missing_town", "valid", "REVIEW_REQUIRED"),
        ("missing_country", "valid", "REVIEW_REQUIRED"),
        ("country_full_name", "invalid", "REVIEW_REQUIRED"),
        ("address_adrline_only", "valid", "REPAIRABLE"),
        ("hybrid_address", "valid", "READY"),
    ],
)
def test_golden_summary(pipeline, fixture, validation, readiness):
    result = pipeline.analyze(load_fixture(fixture), repair=True)
    assert result.original_validation_status == validation
    assert result.address_readiness == readiness


@pytest.mark.parametrize(
    ("fixture", "expected_rule"),
    [
        ("missing_town", "ADR-001"),
        ("missing_country", "ADR-002"),
        ("country_full_name", "ADR-003"),
        ("address_adrline_only", "ADR-004"),
        ("hybrid_address", "ADR-005"),
    ],
)
def test_golden_rule_findings(pipeline, fixture, expected_rule):
    result = pipeline.analyze(load_fixture(fixture), repair=True)
    assert any(f["rule_id"] == expected_rule for f in result.rule_findings)


def test_valid_message_requires_no_repair(pipeline):
    result = pipeline.analyze(load_fixture("valid_structured"), repair=True)
    assert result.candidate_diff == []
    assert result.repair_status == "VALIDATED"
