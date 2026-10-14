"""Unit tests for async batch helpers (no broker/DB required)."""

from __future__ import annotations

from paymentops_api.db.models import BatchJob
from paymentops_api.services.batch_service import _write_counts


def test_write_counts_persists_report_and_counters():
    job = BatchJob()
    counts = {"READY": 3, "REPAIRABLE": 2, "REVIEW_REQUIRED": 1, "UNRESOLVED": 0}
    _write_counts(job, counts, failed=1, total=7, top_rules={"R1": 2, "R2": 1})

    assert job.ready_count == 3
    assert job.repairable_count == 2
    assert job.review_required_count == 1
    assert job.unresolved_count == 0
    assert job.failed_count == 1
    report = job.report
    assert report is not None
    assert report["total_records"] == 7
    assert report["ready"] == 3
    assert report["top_rule_findings"] == [("R1", 2), ("R2", 1)]


def test_write_counts_treats_unknown_readiness_as_unresolved():
    job = BatchJob()
    # Unknown status keys are not written directly; they fall back to 0 via .get().
    counts = {"MYSTERY": 5}
    _write_counts(job, counts, failed=0, total=5, top_rules={})
    assert job.ready_count == 0
    assert job.unresolved_count == 0
    assert job.report["unresolved"] == 0
