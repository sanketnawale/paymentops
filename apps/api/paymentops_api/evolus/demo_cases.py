"""Server-side registry of synthetic demo cases and their supporting evidence.

The investigation tool never accepts filesystem paths, URLs or tenant ids from the model.
Callers pass only a server-issued ``case_ref`` that resolves to one of these bundled,
immutable synthetic payloads.

Phase 2B adds a **synthetic supporting record** per case: an explicit, clearly-labelled
evidence document that links a party to a town name. Repairs may only be proposed from these
values — towns are never derived from country codes or invented.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

_DEMO_DIR = Path(__file__).resolve().parent.parent / "demo_data"

# Parties and fields reachable by a repair proposal (server-side allowlist).
ALLOWED_REPAIR_PARTIES = frozenset({"Dbtr", "Cdtr", "DbtrAgt", "CdtrAgt"})
ALLOWED_REPAIR_FIELDS = frozenset({"TwnNm", "Ctry"})


@dataclass(frozen=True)
class EvidenceEntry:
    """One value from the synthetic supporting record, explicitly linked to a party."""

    ref: str
    party: str  # Dbtr | Cdtr
    field: str  # TwnNm | Ctry
    value: str
    note: str = ""


@dataclass(frozen=True)
class SupportingRecord:
    """A clearly-labelled synthetic supporting record (evidence), not real data."""

    record_id: str
    label: str
    source: str
    entries: tuple[EvidenceEntry, ...] = ()
    # Human-readable notes about what is missing / contradictory (drives review requirement).
    gaps: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    synthetic: bool = True

    def evidence_refs(self) -> set[str]:
        return {e.ref for e in self.entries}

    def entry(self, ref: str) -> EvidenceEntry | None:
        for e in self.entries:
            if e.ref == ref:
                return e
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "record_id": self.record_id,
            "label": self.label,
            "source": self.source,
            "synthetic": self.synthetic,
            "entries": [
                {"ref": e.ref, "party": e.party, "field": e.field, "value": e.value, "note": e.note}
                for e in self.entries
            ],
            "gaps": list(self.gaps),
            "contradictions": list(self.contradictions),
        }


@dataclass(frozen=True)
class DemoCase:
    key: str
    name: str
    message_version: str
    description: str
    filename: str
    origin: str
    supporting_record: SupportingRecord | None = None

    def load(self) -> bytes:
        """Return the immutable synthetic payload bytes."""
        return (_DEMO_DIR / self.filename).read_bytes()

    @property
    def sha256(self) -> str:
        """SHA-256 of the synthetic payload (identity of the input)."""
        return sha256(self.load()).hexdigest()


# Evidence is illustrative synthetic data, explicitly linked to a party. It is NOT derived
# from the country code and is not a real customer record.
_MISSING_TOWN_EVIDENCE = SupportingRecord(
    record_id="SR-1",
    label="Synthetic account master record (town names)",
    source="synthetic master-data extract (demo)",
    entries=(
        EvidenceEntry(
            ref="SR-1:debtor-town",
            party="Dbtr",
            field="TwnNm",
            value="Milano",
            note="Registered town of the debtor account holder",
        ),
        EvidenceEntry(
            ref="SR-1:creditor-town",
            party="Cdtr",
            field="TwnNm",
            value="Roma",
            note="Registered town of the creditor",
        ),
    ),
)

_INCOMPLETE_TOWN_EVIDENCE = SupportingRecord(
    record_id="SR-2",
    label="Synthetic account master record (incomplete / contradictory)",
    source="synthetic master-data extract (demo)",
    entries=(
        EvidenceEntry(
            ref="SR-2:debtor-town",
            party="Dbtr",
            field="TwnNm",
            value="Milano",
            note="Registered town of the debtor account holder",
        ),
    ),
    gaps=(
        "No creditor town is present in the supporting record.",
        "The supporting record contains no value that can be attributed to Cdtr/PstlAdr/TwnNm.",
    ),
    contradictions=(
        "The debtor postal code (20121) is consistent with Milano, but no creditor locality "
        "evidence exists for the creditor address.",
    ),
)


_CASES: dict[str, DemoCase] = {
    "pacs008-valid": DemoCase(
        key="pacs008-valid",
        name="Structured address (clean)",
        message_version="pacs.008.001.08",
        description="Fully structured postal addresses; no expected deterministic rule findings.",
        filename="pacs008_valid.xml",
        origin="tests/fixtures/pacs008/valid_structured.xml",
    ),
    "pacs008-missing-town": DemoCase(
        key="pacs008-missing-town",
        name="Missing town name (repairable)",
        message_version="pacs.008.001.08",
        description=(
            "Debtor and creditor addresses omit TwnNm; expected findings ADR-001. A complete "
            "supporting record supplies both town names, enabling a sandbox repair test."
        ),
        filename="pacs008_missing_town.xml",
        origin="tests/fixtures/pacs008/missing_town.xml",
        supporting_record=_MISSING_TOWN_EVIDENCE,
    ),
    "pacs008-missing-town-incomplete": DemoCase(
        key="pacs008-missing-town-incomplete",
        name="Missing town name (incomplete evidence)",
        message_version="pacs.008.001.08",
        description=(
            "Same payload as the repairable case, but the supporting record is missing the "
            "creditor town (and is contradictory). The creditor town must NOT be invented; the "
            "case requires human review."
        ),
        filename="pacs008_missing_town.xml",
        origin="tests/fixtures/pacs008/missing_town.xml",
        supporting_record=_INCOMPLETE_TOWN_EVIDENCE,
    ),
    "pacs008-hybrid-address": DemoCase(
        key="pacs008-hybrid-address",
        name="Hybrid address",
        message_version="pacs.008.001.08",
        description="Debtor address mixes structured fields with AdrLine; expected ADR-005.",
        filename="pacs008_hybrid_address.xml",
        origin="tests/fixtures/pacs008/hybrid_address.xml",
    ),
}


def list_demo_cases() -> list[DemoCase]:
    return sorted(_CASES.values(), key=lambda c: c.key)


def get_demo_case(key: str) -> DemoCase:
    """Resolve a demo case by key. Raises ``KeyError`` for unknown keys."""
    try:
        return _CASES[key]
    except KeyError:
        raise KeyError(key) from None
