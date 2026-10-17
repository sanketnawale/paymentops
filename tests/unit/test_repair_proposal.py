"""Phase 2B unit tests: evidence, proposal parsing/validation, sandbox apply/revalidation.

These use the REAL engine and the bundled synthetic fixtures (no database, no Evolus).
"""

from __future__ import annotations

import pytest
from paymentops_api.evolus.client import WorkflowExecution
from paymentops_api.evolus.demo_cases import get_demo_case
from paymentops_api.services import repair_service as svc

from address_engine.providers import CloudNovaAddressProvider
from analysis.pipeline import AnalysisPipeline
from iso_engine import build_default_registry
from iso_engine.pacs008.adapter import map_pacs008_to_canonical
from iso_engine.pacs008.identifier import identify_pacs008
from iso_engine.xml_security import secure_parse
from repair_engine.models import ChangeSource, DiffEntry
from repair_engine.xml_reconstruction import apply_changes, serialize
from rules_engine import build_address_ruleset


@pytest.fixture(scope="module")
def pipeline() -> AnalysisPipeline:
    return AnalysisPipeline(
        address_provider=CloudNovaAddressProvider(), rules_engine=build_address_ruleset()
    )


@pytest.fixture(scope="module")
def registry():
    return build_default_registry()


# --------------------------------------------------------------------------- evidence


def test_evidence_records_are_linked_to_parties():
    complete = get_demo_case("pacs008-missing-town").supporting_record
    assert complete is not None
    refs = {e.ref: e for e in complete.entries}
    assert refs["SR-1:debtor-town"].party == "Dbtr"
    assert refs["SR-1:debtor-town"].value == "Milano"
    assert refs["SR-1:creditor-town"].party == "Cdtr"
    assert refs["SR-1:creditor-town"].value == "Roma"

    incomplete = get_demo_case("pacs008-missing-town-incomplete").supporting_record
    assert incomplete is not None
    assert {e.party for e in incomplete.entries} == {"Dbtr"}
    assert incomplete.gaps  # creditor town missing
    assert incomplete.gaps and not incomplete.contradictions  # missing data, not a conflict


# --------------------------------------------------------------------------- validation


def test_validate_accepts_evidence_backed_changes():
    record = get_demo_case("pacs008-missing-town").supporting_record
    allowed, rejected = svc.validate_proposal(
        [
            {"target": "Dbtr/PstlAdr/TwnNm", "value": "Milano", "evidence_ref": "SR-1:debtor-town"},
            {"target": "Cdtr/PstlAdr/TwnNm", "value": "Roma", "evidence_ref": "SR-1:creditor-town"},
        ],
        record,
    )
    assert len(allowed) == 2 and rejected == []


def test_validate_rejects_unsupported_targets():
    record = get_demo_case("pacs008-missing-town").supporting_record
    for target in ("/etc/passwd", "Dbtr/PstlAdr/StrtNm", "Dbtr/Nm", "Document/FIToFICstmrCdtTrf"):
        _allowed, rejected = svc.validate_proposal(
            [{"target": target, "value": "X", "evidence_ref": "SR-1:debtor-town"}], record
        )
        assert rejected and "allowlisted" in rejected[0]["reason"]


def test_validate_rejects_party_mismatch():
    record = get_demo_case("pacs008-missing-town").supporting_record
    _allowed, rejected = svc.validate_proposal(
        [{"target": "Cdtr/PstlAdr/TwnNm", "value": "Milano", "evidence_ref": "SR-1:debtor-town"}],
        record,
    )
    assert rejected and "does not match" in rejected[0]["reason"]


def test_validate_rejects_value_not_matching_evidence():
    record = get_demo_case("pacs008-missing-town").supporting_record
    _allowed, rejected = svc.validate_proposal(
        [{"target": "Dbtr/PstlAdr/TwnNm", "value": "Torino", "evidence_ref": "SR-1:debtor-town"}],
        record,
    )
    assert rejected and "recorded evidence value" in rejected[0]["reason"]


def test_validate_rejects_unknown_ref_and_duplicates():
    record = get_demo_case("pacs008-missing-town").supporting_record
    _allowed, rejected = svc.validate_proposal(
        [{"target": "Dbtr/PstlAdr/TwnNm", "value": "Milano", "evidence_ref": "SR-9:nope"}], record
    )
    assert rejected and rejected[0]["reason"] == "unknown evidence_ref"

    _allowed2, rejected2 = svc.validate_proposal(
        [
            {"target": "Dbtr/PstlAdr/TwnNm", "value": "Milano", "evidence_ref": "SR-1:debtor-town"},
            {"target": "Dbtr/PstlAdr/TwnNm", "value": "Milano", "evidence_ref": "SR-1:debtor-town"},
        ],
        record,
    )
    assert len(rejected2) == 1 and "duplicate" in rejected2[0]["reason"]


def test_incomplete_evidence_cannot_support_creditor_town():
    record = get_demo_case("pacs008-missing-town-incomplete").supporting_record
    allowed, rejected = svc.validate_proposal(
        [{"target": "Cdtr/PstlAdr/TwnNm", "value": "Roma", "evidence_ref": "SR-2:creditor-town"}],
        record,
    )
    assert allowed == [] and rejected and rejected[0]["reason"] == "unknown evidence_ref"


# --------------------------------------------------------------------------- parsing


def test_parse_repair_proposal_from_fenced_json():
    text = (
        "I called the tool. Proposed repair:\n"
        "```json\n"
        '{"proposed_changes": [{"target": "Dbtr/PstlAdr/TwnNm", "value": "Milano", '
        '"evidence_ref": "SR-1:debtor-town"}], "missing_evidence": [], '
        '"recommended_next_step": "review"}\n'
        "```\n"
    )
    execution = WorkflowExecution(
        status="COMPLETED", raw_status="Completed", output_text=text, result=None, raw={}
    )
    proposal = svc.parse_repair_proposal(execution)
    assert proposal["status"] == "PROPOSED"
    assert proposal["changes"][0]["target"] == "Dbtr/PstlAdr/TwnNm"
    assert proposal["recommended_next_step"] == "review"


def test_parse_repair_proposal_unparseable_is_flagged():
    execution = WorkflowExecution(
        status="COMPLETED", raw_status="Completed", output_text="No JSON here.", result=None, raw={}
    )
    proposal = svc.parse_repair_proposal(execution)
    assert proposal["status"] == "PROPOSAL_UNPARSEABLE"
    assert proposal["error"]


def test_parse_final_answer_splits_at_heading():
    text = (
        "Let me think about this.\nThen I will answer.\n\n## Investigation Report\nFindings here."
    )
    execution = WorkflowExecution(
        status="COMPLETED", raw_status="Completed", output_text=text, result=None, raw={}
    )
    answer, reasoning, reliable = svc.parse_final_answer(execution, None)
    assert reliable is True
    assert answer.startswith("## Investigation Report")
    assert reasoning and reasoning.startswith("Let me think")


def test_parse_final_answer_flags_when_unreliable():
    text = "A single paragraph with no heading and no boundary."
    execution = WorkflowExecution(
        status="COMPLETED", raw_status="Completed", output_text=text, result=None, raw={}
    )
    answer, reasoning, reliable = svc.parse_final_answer(execution, None)
    assert reliable is False
    assert answer == text and reasoning is None


def test_parse_final_answer_removes_only_the_proposal_fence():
    fence = '```json\n{"proposed_changes": []}\n```'
    text = f"Reasoning.\n\n## Report\nBody.\n{fence}"
    execution = WorkflowExecution(
        status="COMPLETED", raw_status="Completed", output_text=text, result=None, raw={}
    )
    answer, _reasoning, _reliable = svc.parse_final_answer(execution, fence)
    assert fence not in answer
    assert "## Report" in answer and "Body." in answer


# --------------------------------------------------------------------------- sandbox


def test_sandbox_apply_preserves_original_and_revalidates(pipeline, registry):
    demo = get_demo_case("pacs008-missing-town")
    before = demo.load()
    root = secure_parse(before).root
    version = identify_pacs008(root)
    message = map_pacs008_to_canonical(root, version)
    tx = message.transactions[0]

    entries = [
        DiffEntry(
            path=f"{tx.debtor.postal_address.source_path}/TwnNm",
            before=None,
            after="Milano",
            source=ChangeSource.MANUAL,
        ),
        DiffEntry(
            path=f"{tx.creditor.postal_address.source_path}/TwnNm",
            before=None,
            after="Roma",
            source=ChangeSource.MANUAL,
        ),
    ]
    new_root, applied = apply_changes(root, entries)
    assert all(a.status.value == "VALIDATED" for a in applied)

    # Original payload is unchanged.
    assert demo.load() == before

    sandbox_xml = serialize(new_root)
    sandbox_result = pipeline.analyze_iso(sandbox_xml.encode("utf-8"), registry)
    sandbox_rule_ids = {f["rule_id"] for f in sandbox_result.rule_findings}
    assert "ADR-001" not in sandbox_rule_ids  # both town names now present


def test_evidence_linked_towns_match_sandbox_targets(pipeline, registry):
    """End-to-end: evidence -> validated changes -> sandbox has no ADR-001 remaining."""
    record = get_demo_case("pacs008-missing-town").supporting_record
    allowed, rejected = svc.validate_proposal(
        [
            {"target": "Dbtr/PstlAdr/TwnNm", "value": "Milano", "evidence_ref": "SR-1:debtor-town"},
            {"target": "Cdtr/PstlAdr/TwnNm", "value": "Roma", "evidence_ref": "SR-1:creditor-town"},
        ],
        record,
    )
    assert rejected == []
    demo = get_demo_case("pacs008-missing-town")
    root = secure_parse(demo.load()).root
    message = map_pacs008_to_canonical(root, identify_pacs008(root))
    tx = message.transactions[0]
    entries = [
        DiffEntry(
            path=f"{svc._address_for_party(tx, a['party']).source_path}/{a['field']}",
            before=None,
            after=a["value"],
            source=ChangeSource.MANUAL,
        )
        for a in allowed
    ]
    new_root, _ = apply_changes(root, entries)
    result = pipeline.analyze_iso(serialize(new_root).encode("utf-8"), registry)
    assert "ADR-001" not in {f["rule_id"] for f in result.rule_findings}


# --------------------------------------------------------------------------- placeholder handling

_PLACEHOLDER_BLOCK = (
    '```json\n{"proposed_changes":[{"target":"Dbtr/PstlAdr/TwnNm",'
    '"value":"<value from the record>","evidence_ref":"<evidence_ref>"}],'
    '"missing_evidence":["..."],"recommended_next_step":"..."}\n```'
)
_REAL_BLOCK = (
    '```json\n{"proposed_changes":[{"target":"Dbtr/PstlAdr/TwnNm",'
    '"value":"Bologna","evidence_ref":"SR-NEW-TEST:debtor-town"},'
    '{"target":"Cdtr/PstlAdr/TwnNm","value":"Torino","evidence_ref":"SR-NEW-TEST:creditor-town"}],'
    '"recommended_next_step":"Test on a sandbox copy, then human review."}\n```'
)


def test_parse_proposal_skips_echoed_contract_placeholder_block():
    """The agent may echo the prompt contract; we must pick its real proposal, not placeholders."""
    text = f"Reasoning...\n{_PLACEHOLDER_BLOCK}\n\n## Report\n{_REAL_BLOCK}\n"
    execution = WorkflowExecution(
        status="COMPLETED", raw_status="Completed", output_text=text, result=None, raw={}
    )
    proposal = svc.parse_repair_proposal(execution)
    assert proposal["status"] == "PROPOSED"
    assert [c["value"] for c in proposal["changes"]] == ["Bologna", "Torino"]
    assert all("<" not in c["value"] and "<" not in c["evidence_ref"] for c in proposal["changes"])
    assert proposal["recommended_next_step"] and "..." != proposal["recommended_next_step"]


def test_parse_proposal_placeholder_only_is_unparseable():
    execution = WorkflowExecution(
        status="COMPLETED",
        raw_status="Completed",
        output_text=_PLACEHOLDER_BLOCK,
        result=None,
        raw={},
    )
    proposal = svc.parse_repair_proposal(execution)
    assert proposal["status"] == "PROPOSAL_UNPARSEABLE"
    assert proposal["changes"] == []
    assert proposal["recommended_next_step"] is None


def test_validate_proposal_rejects_placeholders():
    record = get_demo_case("pacs008-missing-town").supporting_record
    allowed, rejected = svc.validate_proposal(
        [
            {
                "target": "Dbtr/PstlAdr/TwnNm",
                "value": "<value from the record>",
                "evidence_ref": "<evidence_ref>",
            }
        ],
        record,
    )
    assert (
        allowed == [] and rejected and rejected[0]["reason"] == "placeholder value or evidence_ref"
    )


# --------------------------------------------------------------------------- structured gaps


def test_parse_proposal_captures_missing_evidence_and_presence():
    """The agent's structured missing_evidence must be captured, and absence distinguished."""
    with_missing = (
        '```json\n{"proposed_changes":[{"target":"Dbtr/PstlAdr/TwnNm","value":"Milano",'
        '"evidence_ref":"SR-1:debtor-town"}],"missing_evidence":["Cdtr/PstlAdr/TwnNm"],'
        '"recommended_next_step":"review"}\n```'
    )
    execution = WorkflowExecution(
        status="COMPLETED", raw_status="Completed", output_text=with_missing, result=None, raw={}
    )
    proposal = svc.parse_repair_proposal(execution)
    assert proposal["missing_evidence"] == ["Cdtr/PstlAdr/TwnNm"]
    assert proposal["missing_evidence_present"] is True

    # _REAL_BLOCK omits the key entirely -> NOT provided (never read as "no evidence missing").
    execution2 = WorkflowExecution(
        status="COMPLETED", raw_status="Completed", output_text=_REAL_BLOCK, result=None, raw={}
    )
    proposal2 = svc.parse_repair_proposal(execution2)
    assert proposal2["missing_evidence"] == []
    assert proposal2["missing_evidence_present"] is False


def test_derive_server_evidence_gaps_for_uncovered_party():
    record = get_demo_case("pacs008-missing-town-incomplete").supporting_record
    findings = [
        {"rule_id": "ADR-001", "target": "Dbtr/PstlAdr"},
        {"rule_id": "ADR-001", "target": "Cdtr/PstlAdr"},
    ]
    # Creditor has no entry and no allowed change -> server-derived gap; debtor is covered.
    gaps = svc.derive_server_evidence_gaps(findings, record, allowed_changes=[])
    assert [g["party"] for g in gaps] == ["Cdtr"]
    assert gaps[0]["provenance"] == "server-derived"

    # A validated creditor change resolves it -> no gap.
    resolved = svc.derive_server_evidence_gaps(
        findings, record, allowed_changes=[{"party": "Cdtr", "field": "TwnNm"}]
    )
    assert resolved == []


def test_merge_evidence_gaps_dedupes_without_losing_provenance():
    merged = svc.merge_evidence_gaps(
        ("supporting_record", ["No creditor town is present."]),
        ("server_derived", ["No creditor town is present."]),
        ("agent", ["Cdtr/PstlAdr/TwnNm"]),
    )
    by_text = {m["gap"]: m for m in merged}
    assert "No creditor town is present." in by_text
    assert sorted(by_text["No creditor town is present."]["provenance"]) == [
        "server_derived",
        "supporting_record",
    ]
    assert len(merged) == 2


# --------------------------------------------------------------------------- empty/clean proposals


def _completed(text: str) -> WorkflowExecution:
    return WorkflowExecution(
        status="COMPLETED", raw_status="Completed", output_text=text, result=None, raw={}
    )


def test_parse_proposal_accepts_explicit_empty_changes():
    """A clean case returns a valid JSON proposal with an empty proposed_changes array."""
    text = (
        "No findings were raised.\n"
        "```json\n"
        '{"proposed_changes": [], "missing_evidence": [], '
        '"recommended_next_step": "Nothing to repair; no sandbox test required."}\n'
        "```\n"
    )
    proposal = svc.parse_repair_proposal(_completed(text))
    assert proposal["status"] == "PROPOSED"
    assert proposal["changes"] == []
    assert proposal["missing_evidence"] == []
    assert proposal["missing_evidence_present"] is True
    assert proposal["recommended_next_step"] == "Nothing to repair; no sandbox test required."


def test_parse_proposal_empty_changes_preserves_missing_evidence_and_next_step():
    text = (
        "```json\n"
        '{"proposed_changes": [], "missing_evidence": ["Cdtr/PstlAdr/TwnNm"], '
        '"recommended_next_step": "Human review for the missing creditor town."}\n'
        "```\n"
    )
    proposal = svc.parse_repair_proposal(_completed(text))
    assert proposal["status"] == "PROPOSED"
    assert proposal["changes"] == []
    assert proposal["missing_evidence"] == ["Cdtr/PstlAdr/TwnNm"]
    assert proposal["recommended_next_step"] == "Human review for the missing creditor town."


def test_parse_proposal_prefers_empty_block_over_echoed_placeholder_block():
    text = (
        f"{_PLACEHOLDER_BLOCK}\n\n"
        '```json\n{"proposed_changes": [], "missing_evidence": [], '
        '"recommended_next_step": "clean"}\n```\n'
    )
    proposal = svc.parse_repair_proposal(_completed(text))
    assert proposal["status"] == "PROPOSED"
    assert proposal["changes"] == []
    assert proposal["recommended_next_step"] == "clean"


def test_parse_proposal_missing_proposed_changes_key_is_unparseable():
    # A JSON object without proposed_changes is not valid structured output.
    proposal = svc.parse_repair_proposal(
        _completed('```json\n{"missing_evidence": [], "recommended_next_step": "x"}\n```')
    )
    assert proposal["status"] == "PROPOSAL_UNPARSEABLE"
    assert proposal["changes"] == []


def test_parse_proposal_malformed_json_is_unparseable():
    proposal = svc.parse_repair_proposal(
        _completed('Reasoning.\n```json\n{"proposed_changes": [ }\n```\n')
    )
    assert proposal["status"] == "PROPOSAL_UNPARSEABLE"


def test_derive_repair_status_distinguishes_clean_from_unresolved():
    # Clean: nothing proposed, no findings.
    assert svc.derive_repair_status("PROPOSED", 0, has_findings=False) == "NO_CHANGES"
    # Unresolved: nothing proposed, but findings remain for review.
    assert svc.derive_repair_status("PROPOSED", 0, has_findings=True) == "REVIEW_REQUIRED"
    # A real proposal stays PROPOSED regardless of findings.
    assert svc.derive_repair_status("PROPOSED", 2, has_findings=True) == "PROPOSED"
    # A non-proposal never becomes a repair state.
    assert svc.derive_repair_status("PROPOSAL_UNPARSEABLE", 0, has_findings=False) == (
        "PROPOSAL_UNPARSEABLE"
    )
    assert svc.derive_repair_status("PROPOSAL_UNPARSEABLE", 0, has_findings=True) == (
        "PROPOSAL_UNPARSEABLE"
    )
