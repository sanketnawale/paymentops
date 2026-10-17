"""Phase 3A unit tests: export evaluation semantics (no database, no model calls).

The Batch Exception Desk export must distinguish "validation actually ran" from "not evaluated",
and must never infer VALIDATED from workflow completion or an empty findings list.
"""

from __future__ import annotations

from paymentops_api.db.models import Investigation
from paymentops_api.services import exception_batch_service as svc


def _inv(
    deterministic_findings: dict[str, object] | None = None,
    repair: dict[str, object] | None = None,
) -> Investigation:
    inv = Investigation()
    inv.deterministic_findings = deterministic_findings
    inv.repair = repair
    return inv


def test_no_investigation_is_not_evaluated():
    assert svc.evaluation_state(None) == (False, None)


def test_recorded_validation_is_evaluated_without_sandbox():
    inv = _inv(deterministic_findings={"rule_findings": [], "original_validation_status": "VALID"})
    assert svc.evaluation_state(inv) == (True, None)


def test_empty_findings_record_is_not_treated_as_evaluated():
    # An empty deterministic_findings object means no recorded validation ran.
    assert svc.evaluation_state(_inv(deterministic_findings={})) == (False, None)


def test_sandbox_review_status_is_reported_verbatim():
    inv = _inv(
        deterministic_findings={"rule_findings": [{"rule_id": "ADR-001"}]},
        repair={"status": "VALIDATED", "test": {"review_status": "VALIDATED"}},
    )
    assert svc.evaluation_state(inv) == (True, "VALIDATED")


def test_repair_without_a_test_has_no_sandbox_status():
    inv = _inv(
        deterministic_findings={"rule_findings": [{"rule_id": "ADR-001"}]},
        repair={"status": "PROPOSED", "proposal": {"status": "PROPOSED"}},
    )
    assert svc.evaluation_state(inv) == (True, None)
