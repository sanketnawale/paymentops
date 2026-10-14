"""Server-side registry of synthetic demo cases.

The investigation tool never accepts filesystem paths, URLs or tenant ids from the model.
Callers pass only a server-issued ``case_ref`` that resolves to one of these bundled,
immutable synthetic payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

_DEMO_DIR = Path(__file__).resolve().parent.parent / "demo_data"


# Origins are documented in demo_data/README.md (copies of existing synthetic test fixtures).
@dataclass(frozen=True)
class DemoCase:
    key: str
    name: str
    message_version: str
    description: str
    filename: str
    origin: str

    def load(self) -> bytes:
        """Return the immutable synthetic payload bytes."""
        return (_DEMO_DIR / self.filename).read_bytes()

    @property
    def sha256(self) -> str:
        """SHA-256 of the synthetic payload (identity of the input)."""
        return sha256(self.load()).hexdigest()


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
        name="Missing town name",
        message_version="pacs.008.001.08",
        description="Creditor address omits TwnNm; expected finding ADR-001 (town name missing).",
        filename="pacs008_missing_town.xml",
        origin="tests/fixtures/pacs008/missing_town.xml",
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
