"""Unit tests for the investigation validation core.

These use the REAL deterministic PaymentOps engine against bundled synthetic fixtures
(no database, no Evolus/AMD). They prove the validation is performed by the engine, that
findings carry real rule identifiers and field locations, and that the input is not mutated.
"""

from __future__ import annotations

import pytest
from paymentops_api.evolus.client import WorkflowExecution
from paymentops_api.evolus.demo_cases import get_demo_case, list_demo_cases
from paymentops_api.services import investigation_service as svc

from address_engine.providers import CloudNovaAddressProvider
from analysis.pipeline import AnalysisPipeline
from iso_engine import build_default_registry
from rules_engine import build_address_ruleset


@pytest.fixture(scope="module")
def pipeline() -> AnalysisPipeline:
    return AnalysisPipeline(
        address_provider=CloudNovaAddressProvider(), rules_engine=build_address_ruleset()
    )


@pytest.fixture(scope="module")
def registry():
    return build_default_registry()


def _validate(pipeline: AnalysisPipeline, registry, key: str):
    demo = get_demo_case(key)
    result = svc.run_deterministic_validation(demo.load(), pipeline=pipeline, registry=registry)
    return demo, result


def test_demo_case_registry_is_server_side_and_documented():
    keys = {c.key for c in list_demo_cases()}
    assert {"pacs008-valid", "pacs008-missing-town", "pacs008-hybrid-address"} <= keys
    for case in list_demo_cases():
        assert case.message_version == "pacs.008.001.08"
        assert len(case.sha256) == 64
        assert case.origin.startswith("tests/fixtures/")
    with pytest.raises(KeyError):
        get_demo_case("../../etc/passwd")


def test_real_engine_reports_version_and_schema(pipeline, registry):
    demo, result = _validate(pipeline, registry, "pacs008-valid")
    assert result.message_version == "pacs.008.001.08"
    assert result.schema_validation is True
    assert result.original_validation_status == "valid"
    assert result.engine_version
    # A structurally valid message with structured addresses still routes through the engine;
    # we never assert "no findings" as proof of safety, only the engine's own output.
    assert isinstance(result.rule_findings, list)


def test_missing_town_produces_adr001_with_field_location(pipeline, registry):
    _demo, result = _validate(pipeline, registry, "pacs008-missing-town")
    findings = {f["rule_id"]: f for f in result.rule_findings}
    assert "ADR-001" in findings
    finding = findings["ADR-001"]
    assert finding["ruleset_version"] == "cloudnova-address-v1"
    assert finding["target"].endswith("/PstlAdr")
    assert finding["severity"] == "WARNING"


def test_hybrid_address_produces_adr005(pipeline, registry):
    _demo, result = _validate(pipeline, registry, "pacs008-hybrid-address")
    rule_ids = {f["rule_id"] for f in result.rule_findings}
    assert "ADR-005" in rule_ids


def test_tool_payload_separates_validation_from_interpretation(pipeline, registry):
    demo, result = _validate(pipeline, registry, "pacs008-missing-town")
    input_sha = svc.payload_sha256(demo.load())
    payload = svc.build_tool_validation_payload(
        case_ref="inv-test",
        demo=demo,
        result=result,
        input_sha256=input_sha,
        profile_version=None,
    )
    assert payload["tool"] == "paymentops.validate_case"
    assert payload["case_ref"] == "inv-test"
    assert payload["synthetic"] is True
    assert payload["input"]["identity_sha256"] == input_sha
    assert payload["input"]["input_unchanged"] is True
    assert payload["validation"]["status"] == "valid"
    assert any(f["rule_id"] == "ADR-001" for f in payload["validation"]["findings"])
    guidance = payload["interpretation_guidance"]
    assert guidance["authoritative"] is True
    assert "do not establish payment safety" in guidance["note"]


def test_validation_does_not_mutate_the_input(pipeline, registry):
    demo = get_demo_case("pacs008-missing-town")
    before = demo.load()
    svc.run_deterministic_validation(before, pipeline=pipeline, registry=registry)
    assert demo.load() == before
    assert svc.payload_sha256(demo.load()) == svc.payload_sha256(before)


def test_parse_agent_result_extracts_cited_rules_from_text():
    execution = WorkflowExecution(
        status="COMPLETED",
        raw_status="Completed",
        output_text="Reviewed ADR-001 and ISO-002; no other issues found.",
        result=None,
        raw={},
    )
    parsed = svc.parse_agent_result(execution)
    assert set(parsed["cited_rules"]) == {"ADR-001", "ISO-002"}
    assert parsed["explanation"] == execution.output_text


def test_parse_agent_result_prefers_structured_fields():
    execution = WorkflowExecution(
        status="COMPLETED",
        raw_status="Completed",
        output_text=None,
        result={
            "summary": "Two findings",
            "cited_rules": ["ADR-001", "ADR-005"],
            "missing_evidence": ["No sanctions data available"],
            "recommended_next_step": "Route to a human reviewer",
        },
        raw={"status": "Completed"},
    )
    parsed = svc.parse_agent_result(execution)
    assert parsed["explanation"] == "Two findings"
    assert parsed["cited_rules"] == ["ADR-001", "ADR-005"]
    assert parsed["missing_evidence"] == ["No sanctions data available"]
    assert parsed["recommended_next_step"] == "Route to a human reviewer"
    assert parsed["raw"] == {"status": "Completed"}


def test_parse_agent_result_ignores_rule_catalog_table():
    """Regression: the agent echoes the rules KB as a markdown table.

    Observed real output echoed the catalogue (``| `ADR-002` | Country missing | ERROR |``),
    which must not be reported as cited findings for the case.
    """
    output = (
        "Reasoning preamble...\n"
        "### Findings\n"
        "- Two `ADR-001` warnings at Dbtr/PstlAdr and Cdtr/PstlAdr.\n"
        "### Rule catalogue\n"
        "| Rule | Name | Severity |\n"
        "| --- | --- | --- |\n"
        "| `ADR-001` | Town name missing | WARNING |\n"
        "| `ADR-002` | Country missing | ERROR |\n"
        "| `ADR-003` | Country code invalid | ERROR |\n"
    )
    execution = WorkflowExecution(
        status="COMPLETED", raw_status="Completed", output_text=output, result=None, raw={}
    )
    parsed = svc.parse_agent_result(execution)
    assert parsed["cited_rules"] == ["ADR-001"]
    # The full report text is preserved verbatim (no broad filtering of report content).
    assert parsed["explanation"] == output


def test_parse_agent_result_constrains_citations_to_engine_findings():
    """Regression: a real run echoed rule ids in prose; constrain to engine findings."""
    output = (
        "Summary of the case. The finding is ADR-001; for completeness ADR-002 and ISO-003 "
        "also exist in the ruleset.\n"
    )
    execution = WorkflowExecution(
        status="COMPLETED", raw_status="Completed", output_text=output, result=None, raw={}
    )
    parsed = svc.parse_agent_result(execution, engine_rule_ids={"ADR-001"})
    assert parsed["cited_rules"] == ["ADR-001"]
    # Without the engine constraint, extraction is best-effort and returns all mentions.
    loose = svc.parse_agent_result(execution)
    assert set(loose["cited_rules"]) == {"ADR-001", "ADR-002", "ISO-003"}
