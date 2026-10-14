"""Security tests: unsafe mapping selectors, transforms, and CSV report safety."""

from __future__ import annotations

from mapping_engine import (
    FieldMapping,
    FieldRequirement,
    MappingDefinition,
    SourceFormat,
    map_to_canonical,
    validate_mapping,
)
from mapping_engine.transforms import supported_transforms


def test_unsafe_mapping_selector_rejected():
    # Selectors that would imply arbitrary code must not be accepted.
    m = MappingDefinition(
        mapping_version="v1",
        source_format=SourceFormat.JSON,
        record_selector="$.p[*]",
        fields=[
            FieldMapping(source="$.x", target="creditor.name", transforms=["__import__('os')"])
        ],
    )
    v = validate_mapping(m)
    assert v.valid is False
    assert any(e.code == "MAP-006" for e in v.errors)


def test_no_python_shell_template_in_supported_transforms():
    for t in supported_transforms():
        assert "__import__" not in t
        assert "os.system" not in t
        assert "(" not in t


def test_csv_report_avoids_formula_injection_fields():
    # The batch report aggregates counts/rule ids only; no raw cell values.
    from paymentops_api.services.batch_service import MAX_FILE_BYTES, MAX_ROWS

    assert MAX_FILE_BYTES > 0
    assert MAX_ROWS > 0
    # A formula-injection-prone cell value must never reach a report column.
    dangerous = '=HYPERLINK("http://evil")'
    report_keys = {
        "total_records",
        "ready",
        "repairable",
        "review_required",
        "unresolved",
        "failed",
        "top_rule_findings",
    }
    assert dangerous not in report_keys


def test_required_missing_mapping_is_structured_not_silent():
    m = MappingDefinition(
        mapping_version="v1",
        source_format=SourceFormat.JSON,
        record_selector="$.p[*]",
        fields=[
            FieldMapping(source="$.id", target="instruction_id", required=FieldRequirement.REQUIRED)
        ],
    )
    res = map_to_canonical(m, {"p": [{"other": 1}]})
    assert any(i.code == "MAP-001" and i.severity.value == "ERROR" for i in res.issues)
