"""Phase 2B sandbox repair: proposal parsing, strict server-side validation, sandbox test.

Safety model
------------
- The agent may only *propose* changes. It never supplies filesystem paths or code.
- A proposal is a list of ``{target, value, evidence_ref}`` entries where ``target`` is a
  party-scoped field (``Dbtr/PstlAdr/TwnNm``). The server resolves the real XML path itself.
- Every change is validated against the case's synthetic supporting record: the target must be
  allowlisted, the ``evidence_ref`` must exist and match the target's party/field, and the value
  must equal the recorded evidence value. Unsupported/conflicting changes are rejected.
- The sandbox copy is produced with the existing ``repair_engine`` (deep copy, allowlisted
  ``PostalAddress24`` leaves only). The original payload is never mutated.
- The sandbox is re-validated with the *real* deterministic engine (XSD + rules + address).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from paymentops_api.db.models import AuditEvent, Investigation
from paymentops_api.evolus.client import WorkflowExecution
from paymentops_api.evolus.demo_cases import SupportingRecord
from paymentops_api.logging import get_logger
from paymentops_api.observability import repair_tests_total
from paymentops_api.services.case_payload import load_payload, load_record
from sqlalchemy.ext.asyncio import AsyncSession

from analysis.pipeline import AnalysisPipeline
from iso_engine.pacs008.adapter import map_pacs008_to_canonical
from iso_engine.pacs008.identifier import identify_pacs008
from iso_engine.registry import IsoMessageRegistry
from iso_engine.xml_security import secure_parse
from repair_engine.models import ChangeSource, DiffEntry
from repair_engine.xml_reconstruction import apply_changes, serialize
from rules_engine import RULESET_VERSION

logger = get_logger("paymentops.repair")

_TARGET_RE = re.compile(r"^(Dbtr|Cdtr|DbtrAgt|CdtrAgt)/PstlAdr/(TwnNm|Ctry)$")
_ADDRESS_PARTY_RE = re.compile(r"^(Dbtr|Cdtr|DbtrAgt|CdtrAgt)/PstlAdr$")
_SEVERITIES_BLOCKING = {"ERROR", "CRITICAL"}
_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


# --------------------------------------------------------------------------- prompt contract


def build_evidence_block(record: SupportingRecord | None) -> str:
    """Render the synthetic supporting record for the workflow input (non-secret)."""
    if record is None:
        return "SUPPORTING RECORD: none provided for this case."
    lines = [
        f"SUPPORTING RECORD {record.record_id} ({record.label}) - SYNTHETIC demo data, not real:",
        f"  source: {record.source}",
    ]
    for e in record.entries:
        lines.append(
            f"  - evidence_ref={e.ref} | party={e.party} | field={e.field} | value={e.value}"
        )
    for gap in record.gaps:
        lines.append(f"  GAP: {gap}")
    for contradiction in record.contradictions:
        lines.append(f"  CONTRADICTION: {contradiction}")
    return "\n".join(lines)


def build_proposal_contract() -> str:
    """The exact structured-proposal contract the agent must emit (fenced JSON)."""
    return (
        "After the validation result is available, propose repairs ONLY from the supporting "
        "record. Output a single fenced json block exactly in this shape:\n"
        "```json\n"
        "{\n"
        '  "proposed_changes": [\n'
        '    {"target": "Dbtr/PstlAdr/TwnNm", "value": "<value from the record>", '
        '"evidence_ref": "<evidence_ref>"}\n'
        "  ],\n"
        '  "missing_evidence": ["..."],\n'
        '  "recommended_next_step": "..."\n'
        "}\n"
        "```\n"
        "Rules for the proposal:\n"
        "- `target` must be `<party>/PstlAdr/<TwnNm|Ctry>` with party in "
        "{Dbtr, Cdtr, DbtrAgt, CdtrAgt}.\n"
        "- `value` MUST equal the value recorded for `evidence_ref`. Never invent or derive a "
        "value (do not infer a town from a country code).\n"
        "- `evidence_ref` must be one of the refs in the supporting record.\n"
        "- If no evidence supports a missing field, omit it and list it under `missing_evidence`; "
        "do not propose a value for it.\n"
        "- ALWAYS include the `missing_evidence` array in the JSON. List every finding target that "
        "has no supporting-record evidence (so no value can be proposed). Use an empty array ONLY "
        "when no target lacks evidence — an empty array is a positive claim, not a default.\n"
        "Definitions and cautions:\n"
        "- A field **absent from the payment XML but present in the supporting record is MISSING "
        "DATA, not a conflict**.\n"
        "- A **conflict** requires *incompatible evidence for the same party/field* (e.g. two "
        "different recorded values, or evidence that disagrees with the message).\n"
        "- The **absence of a rule finding does NOT mean every related check passed**; a rule not "
        "cited was not evaluated as passing.\n"
        "- **Supported message versions are still XSD-validated**; report schema validity "
        "separately from rule findings.\n"
        "- Evidence supports **only the specified proposed changes**; do not claim that no other "
        "evidence is needed in general.\n"
        "- Recommend **sandbox testing before human review**, and clearly distinguish "
        "**proposed changes** from **tested results** (proposed != validated).\n"
    )


# --------------------------------------------------------------------------- parsing


_PLACEHOLDER_RE = re.compile(r"^\s*<[^>]*>\s*$")


def _is_placeholder(value: str | None) -> bool:
    """True for template placeholders like ``<value from the record>``, ``...`` or empty."""
    if value is None:
        return True
    text = value.strip()
    if not text or text in {"...", "…"}:
        return True
    return bool(_PLACEHOLDER_RE.match(text))


def _iter_fenced_json(text: str) -> list[tuple[dict[str, Any], str]]:
    """Return every fenced JSON object in ``text`` (the model may echo the prompt contract)."""
    found: list[tuple[dict[str, Any], str]] = []
    for match in _FENCE_RE.finditer(text):
        try:
            obj = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            found.append((obj, match.group(0)))
    return found


def _find_json_with_key(text: str, key: str) -> dict[str, Any] | None:
    """Scan for a balanced ``{...}`` object containing ``key`` (fallback parser)."""
    for start in (m.start() for m in re.finditer(r"\{", text)):
        depth = 0
        for end in range(start, len(text)):
            if text[end] == "{":
                depth += 1
            elif text[end] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : end + 1]
                    try:
                        obj = json.loads(candidate)
                    except json.JSONDecodeError:
                        break
                    if isinstance(obj, dict) and key in obj:
                        return obj
                    break
    return None


def _normalise_change(item: Any) -> dict[str, str] | None:
    if not isinstance(item, dict):
        return None
    return {
        "target": str(item.get("target") or "").strip(),
        "value": str(item.get("value") or "").strip(),
        "evidence_ref": str(item.get("evidence_ref") or "").strip(),
    }


def _usable_changes(obj: dict[str, Any]) -> list[dict[str, str]]:
    """Return the non-placeholder changes from a candidate object (may be empty)."""
    raw = obj.get("proposed_changes")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        change = _normalise_change(item)
        if change is None:
            continue
        # Never store template placeholders or otherwise fabricated values.
        if _is_placeholder(change["value"]) or _is_placeholder(change["evidence_ref"]):
            continue
        out.append(change)
    return out


def parse_repair_proposal(execution: WorkflowExecution) -> dict[str, Any]:
    """Parse the agent's structured repair proposal. Never raises; always returns a dict.

    Scans ALL fenced JSON blocks and selects the agent's **real, non-placeholder** proposal. The
    contract template injected into the prompt is sometimes echoed back by the model; we must
    never store its placeholders and never fabricate a proposal.
    """
    text = execution.output_text or ""
    best: tuple[dict[str, Any], str | None] | None = None
    for obj, raw in _iter_fenced_json(text):
        if _usable_changes(obj):
            best = (obj, raw)  # prefer the last valid block (agent's final proposal)
    if best is None:
        fallback = _find_json_with_key(text, "proposed_changes")
        if fallback is not None and _usable_changes(fallback):
            best = (fallback, None)
    if best is None:
        return {
            "status": "PROPOSAL_UNPARSEABLE",
            "error": "No non-placeholder structured repair proposal was found in the agent output.",
            "changes": [],
            "missing_evidence": [],
            "missing_evidence_present": False,
            "recommended_next_step": None,
            "raw_block": None,
        }
    obj, raw_block = best
    missing = obj.get("missing_evidence")
    next_step = obj.get("recommended_next_step")
    next_step_str = str(next_step) if next_step is not None else ""
    # ``missing_evidence_present`` distinguishes "the agent supplied an (empty) array" from "the
    # agent omitted the key". An absent list must never be read as "no evidence missing".
    return {
        "status": "PROPOSED",
        "error": None,
        "changes": _usable_changes(obj),
        "missing_evidence": [str(x) for x in missing] if isinstance(missing, list) else [],
        "missing_evidence_present": isinstance(missing, list),
        "recommended_next_step": None if _is_placeholder(next_step_str) else next_step_str,
        "raw_block": raw_block,
    }


def parse_final_answer(
    execution: WorkflowExecution, proposal_raw_block: str | None
) -> tuple[str, str | None, bool]:
    """Narrowly separate the user-facing answer from inline reasoning.

    Observed format: the agent's ``output`` begins with reasoning prose and then a markdown
    report. We split at the first markdown heading *after* some prose. If no such boundary
    exists, separation is reported as unreliable (the caller keeps the full text; nothing is
    silently deleted). The parsed JSON proposal fence is removed because it is machine data
    displayed separately.
    """
    text = execution.output_text or ""
    if proposal_raw_block:
        text = text.replace(proposal_raw_block, "").strip()
    match = re.search(r"(?m)^#{1,3}\s+\S", text)
    if match and match.start() > 0:
        reasoning = text[: match.start()].strip() or None
        answer = text[match.start() :].strip()
        return answer, reasoning, True
    return text.strip(), None, False


# --------------------------------------------------------------------------- validation


def validate_proposal(
    changes: list[dict[str, str]], record: SupportingRecord | None
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Validate proposed changes against the supporting record. Returns (allowed, rejected)."""
    allowed: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []
    if record is None:
        return [], [
            {
                "target": c.get("target", ""),
                "value": c.get("value", ""),
                "reason": "no supporting record",
            }
            for c in changes
        ]
    seen: dict[str, str] = {}
    for change in changes:
        target = change.get("target", "")
        value = change.get("value", "")
        ref = change.get("evidence_ref", "")
        reason: str | None = None
        match = _TARGET_RE.fullmatch(target)
        if _is_placeholder(value) or _is_placeholder(ref):
            reason = "placeholder value or evidence_ref"
        elif not match:
            reason = "target is not an allowlisted party/field"
        elif not value:
            reason = "value is empty"
        elif target in seen:
            reason = "duplicate target (conflicting proposal)"
        else:
            party, field = match.group(1), match.group(2)
            entry = record.entry(ref)
            if entry is None:
                reason = "unknown evidence_ref"
            elif entry.party != party or entry.field != field:
                reason = "evidence_ref does not match the target party/field"
            elif entry.value.strip().casefold() != value.casefold():
                reason = "proposed value does not match the recorded evidence value"
            else:
                seen[target] = value
                allowed.append(
                    {
                        "target": target,
                        "party": party,
                        "field": field,
                        "value": entry.value,
                        "evidence_ref": ref,
                    }
                )
        if reason is not None:
            rejected.append(
                {"target": target, "value": value, "evidence_ref": ref, "reason": reason}
            )
    return allowed, rejected


def derive_server_evidence_gaps(
    findings: list[dict[str, Any]] | None,
    record: SupportingRecord | None,
    allowed_changes: list[dict[str, Any]] | None,
) -> list[dict[str, str]]:
    """Server-derived evidence gaps.

    A finding that requires an evidence-backed change, whose party has no matching entry in the
    supporting record (and no validated change resolves it), is a *server-derived* gap. These are
    computed here (never invented from the agent's narrative) and only for allowlisted address
    repair targets.
    """
    if record is None:
        return []
    covered_parties = {e.party for e in record.entries}
    resolved_parties = {
        str(c.get("party"))
        for c in (allowed_changes or [])
        if isinstance(c, dict) and c.get("party")
    }
    gaps: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for finding in findings or []:
        if not isinstance(finding, dict):
            continue
        target = str(finding.get("target") or "")
        rule_id = str(finding.get("rule_id") or "")
        match = _ADDRESS_PARTY_RE.fullmatch(target)
        if not match:
            continue
        party = match.group(1)
        if party in resolved_parties or party in covered_parties:
            continue
        key = (rule_id, party)
        if key in seen:
            continue
        seen.add(key)
        gaps.append(
            {
                "gap": (
                    f"No supporting-record evidence for {party} postal address ({rule_id}); "
                    "no evidence-backed value can be proposed."
                ),
                "provenance": "server-derived",
                "rule_id": rule_id,
                "party": party,
            }
        )
    return gaps


def merge_evidence_gaps(*sources: tuple[str, list[str]]) -> list[dict[str, Any]]:
    """Deduplicate equivalent gap texts while keeping every source (provenance)."""
    merged: dict[str, dict[str, Any]] = {}
    for provenance, values in sources:
        for value in values or []:
            text = str(value).strip()
            if not text:
                continue
            key = text.casefold()
            entry = merged.setdefault(key, {"gap": text, "provenance": []})
            if provenance not in entry["provenance"]:
                entry["provenance"].append(provenance)
    return list(merged.values())


def _address_for_party(transaction: Any, party: str) -> Any:
    if party == "Dbtr" and transaction.debtor:
        return transaction.debtor.postal_address
    if party == "Cdtr" and transaction.creditor:
        return transaction.creditor.postal_address
    if party == "DbtrAgt" and transaction.debtor_agent:
        return transaction.debtor_agent.postal_address
    if party == "CdtrAgt" and transaction.creditor_agent:
        return transaction.creditor_agent.postal_address
    return None


def _severity_blocking(findings: list[dict[str, Any]]) -> bool:
    return any(str(f.get("severity", "")).upper() in _SEVERITIES_BLOCKING for f in findings)


def _finding_key(finding: dict[str, Any]) -> tuple[str, str]:
    return (str(finding.get("rule_id", "")), str(finding.get("target", "")))


# --------------------------------------------------------------------------- sandbox test


async def test_repair(
    session: AsyncSession,
    inv: Investigation,
    *,
    pipeline: AnalysisPipeline,
    registry: IsoMessageRegistry,
) -> Investigation:
    """Apply allowlisted changes to a sandbox copy and re-validate with the real engine."""
    record = load_record(inv)
    repair: dict[str, Any] = dict(inv.repair or {})
    proposal: dict[str, Any] = dict(repair.get("proposal") or {})
    changes = proposal.get("changes") or []

    allowed, rejected = validate_proposal(changes, record)

    # Resolve real XML paths from the canonical model (the agent never supplies paths).
    original_root = secure_parse(load_payload(inv)).root
    version = identify_pacs008(original_root)
    message = map_pacs008_to_canonical(original_root, version)
    if len(message.transactions) != 1:
        rejected = rejected + [
            {
                "target": c["target"],
                "value": c["value"],
                "reason": "repair supports single-transaction messages only",
            }
            for c in allowed
        ]
        allowed = []

    applied: list[dict[str, Any]] = []
    diff_entries: list[DiffEntry] = []
    for change in allowed:
        address = _address_for_party(message.transactions[0], change["party"])
        if address is None or not address.source_path:
            rejected.append({**change, "reason": "target address not present in the message"})
            continue
        path = f"{address.source_path}/{change['field']}"
        before = address.original_fields.get(change["field"])
        # Skip a no-op change (value already equal) — not an error, just nothing to apply.
        if (before or "").casefold() == change["value"].casefold():
            applied.append(
                {**change, "path": path, "before": before, "after": change["value"], "noop": True}
            )
            continue
        diff_entries.append(
            DiffEntry(path=path, before=before, after=change["value"], source=ChangeSource.MANUAL)
        )
        applied.append(
            {**change, "path": path, "before": before, "after": change["value"], "noop": False}
        )

    raw_before = (inv.deterministic_findings or {}).get("rule_findings")
    before_findings = raw_before if isinstance(raw_before, list) else []
    sandbox_test: dict[str, Any] | None = None
    if diff_entries:
        # Reconstruct the sandbox from the ORIGINAL tree (never mutating it), then re-validate.
        new_root, _applied_entries = apply_changes(original_root, diff_entries)
        sandbox_xml = serialize(new_root)
        sandbox_result = pipeline.analyze_iso(sandbox_xml.encode("utf-8"), registry)
        after_findings = sandbox_result.rule_findings
        # A sandbox repair is only "validated" when it resolves ALL original findings. Any
        # original finding still present (e.g. a field with no supporting evidence, so no
        # change could be proposed) forces human review.
        before_keys = {_finding_key(f) for f in before_findings if isinstance(f, dict)}
        after_keys = {_finding_key(f) for f in after_findings if isinstance(f, dict)}
        unresolved_keys = sorted(before_keys & after_keys)
        unresolved = [{"rule_id": rid, "target": target} for (rid, target) in unresolved_keys]
        if (
            sandbox_result.schema_validation
            and not _severity_blocking(after_findings)
            and not unresolved
            and not rejected
        ):
            review_status = "VALIDATED"
        else:
            review_status = "REVIEW_REQUIRED"
        sandbox_test = {
            "sandbox_id": f"SBX-{uuid4().hex[:12]}",
            "original_hash": inv.input_hash,
            "sandbox_hash": hashlib.sha256(sandbox_xml.encode("utf-8")).hexdigest(),
            "applied_changes": [a for a in applied if not a.get("noop")],
            "before_findings": before_findings,
            "after_findings": after_findings,
            "remaining_issues": after_findings,
            "unresolved_findings": unresolved,
            "xsd_valid": sandbox_result.schema_validation,
            "review_status": review_status,
            "revalidated_by": f"paymentops-engine {sandbox_result.engine_version}",
            "ruleset_version": RULESET_VERSION,
            "tested_at": datetime.now(UTC).isoformat(),
            "disclaimer": (
                "Deterministic re-validation of a sandbox copy. This is not payment "
                "authorization, settlement readiness, or proof of payment safety."
            ),
        }

    if sandbox_test and sandbox_test["review_status"] == "VALIDATED" and not rejected:
        status = "VALIDATED"
    elif sandbox_test:
        status = "REVIEW_REQUIRED"
    elif rejected:
        status = "REJECTED"
    elif before_findings:
        # Nothing was proposed/applied but the original message still has unresolved findings
        # (e.g. missing evidence) -> a human must review.
        status = "REVIEW_REQUIRED"
    else:
        status = "NO_CHANGES"

    repair["status"] = status
    repair["validated_changes"] = applied
    repair["rejected_changes"] = rejected
    repair["test"] = sandbox_test
    repair["tested_at"] = datetime.now(UTC).isoformat()
    inv.repair = repair
    inv.updated_at = datetime.now(UTC)
    repair_tests_total.labels(status=status).inc()
    session.add(
        AuditEvent(
            organization_id=inv.organization_id,
            case_id=inv.investigation_id,
            event_type="repair.test",
            action_metadata={
                "classification": status,
                "applied": len(applied),
                "rejected": len(rejected),
            },
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()
    await session.refresh(inv)
    return inv
