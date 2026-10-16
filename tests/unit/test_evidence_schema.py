"""Phase 2C unit tests: uploaded-evidence schema validation."""

from __future__ import annotations

import pytest
from paymentops_api.evolus.demo_cases import build_supporting_record, record_from_stored


def _valid() -> dict[str, object]:
    return {
        "record_id": "SR-UP-1",
        "label": "Synthetic record",
        "source": "uploaded",
        "entries": [
            {"ref": "a", "party": "Dbtr", "field": "TwnNm", "value": "Milano"},
            {"ref": "b", "party": "Cdtr", "field": "TwnNm", "value": "Roma"},
        ],
    }


def test_valid_evidence_builds_and_round_trips():
    record = build_supporting_record(_valid())
    assert record.entry("a").party == "Dbtr"
    assert record.entry("b").value == "Roma"
    again = record_from_stored(record.to_dict())
    assert again is not None and again.entry("a").value == "Milano"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(entries="not-a-list"),
        lambda d: d.update(entries=[{"ref": "", "party": "Dbtr", "field": "TwnNm", "value": "x"}]),
        lambda d: d.update(
            entries=[{"ref": "a", "party": "Hacker", "field": "TwnNm", "value": "x"}]
        ),
        lambda d: d.update(entries=[{"ref": "a", "party": "Dbtr", "field": "Nm", "value": "x"}]),
        lambda d: d.update(
            entries=[
                {"ref": "a", "party": "Dbtr", "field": "TwnNm", "value": "x"},
                {"ref": "a", "party": "Cdtr", "field": "TwnNm", "value": "y"},
            ]
        ),
    ],
)
def test_invalid_evidence_is_rejected(mutate):
    data = _valid()
    mutate(data)
    with pytest.raises(ValueError):
        build_supporting_record(data)


def test_record_from_stored_handles_none_and_garbage():
    assert record_from_stored(None) is None
    assert record_from_stored({"entries": "bad"}) is None
