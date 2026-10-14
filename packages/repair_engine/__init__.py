"""CloudNova repair engine: candidate generation + XML reconstruction + diff."""

from __future__ import annotations

from repair_engine.generator import generate_candidate
from repair_engine.models import (
    ChangeSource,
    ChangeStatus,
    DiffEntry,
    RepairCandidate,
)
from repair_engine.xml_reconstruction import apply_changes, serialize

__all__ = [
    "ChangeSource",
    "ChangeStatus",
    "DiffEntry",
    "RepairCandidate",
    "apply_changes",
    "generate_candidate",
    "serialize",
]
