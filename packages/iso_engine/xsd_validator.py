"""Deterministic XSD validation.

The schema is bundled and versioned under ``schemas/iso20022/``. Schemas are compiled once
and cached (thread-safe). Validation runs against the *original* secure XML tree before any
deeper processing. The XML/XSD validator is authoritative; it is never overridden by LLM or
heuristic output.

Validation issues are machine-readable (code, severity, path). ``path`` is an XPath or the
best available location.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from lxml import etree

from iso_engine.pacs008.namespace import SupportedVersion

# Repository root: packages/iso_engine/xsd_validator.py -> parents[2] == repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
# Schema root is overridable (e.g. a container path) via PAYMENTOPS_SCHEMA_DIR.
_SCHEMA_ROOT = Path(
    os.environ.get("PAYMENTOPS_SCHEMA_DIR") or str(_REPO_ROOT / "schemas" / "iso20022")
)

ISSUE_CODE_INVALID = "ISO-XSD-001"


@dataclass(frozen=True)
class SchemaIssue:
    code: str
    severity: str  # ERROR | WARNING
    path: str | None
    message: str


@dataclass(frozen=True)
class SchemaValidationResult:
    valid: bool
    schema_version: str
    issues: list[SchemaIssue] = field(default_factory=list)


class XsdValidator:
    """Validate XML against a bundled ISO 20022 subset schema."""

    def __init__(self, schema_path: Path) -> None:
        self.schema_path = schema_path
        self.schema_version = schema_path.stem
        with open(schema_path, "rb") as fh:
            schema_doc = etree.parse(fh)
        self._schema = etree.XMLSchema(schema_doc)

    def validate(self, root: etree._Element) -> SchemaValidationResult:
        ok = self._schema.validate(root)
        issues: list[SchemaIssue] = []
        if not ok:
            # lxml's error_log is iterable at runtime; the type stubs omit __iter__.
            for error in self._schema.error_log:  # type: ignore[attr-defined]
                issues.append(
                    SchemaIssue(
                        code=ISSUE_CODE_INVALID,
                        severity="ERROR",
                        path=_error_path(error),
                        message=_safe_message(error),
                    )
                )
        return SchemaValidationResult(
            valid=ok,
            schema_version=self.schema_version,
            issues=issues,
        )


def _error_path(error: etree._LogEntry) -> str | None:
    # lxml exposes an XPath-like path on newer versions; fall back to line number.
    path = getattr(error, "path", None)
    if path:
        return str(path)
    return f"[line {error.line}]"


def _safe_message(error: etree._LogEntry) -> str:
    # Error messages may quote a fragment of the document; keep it short and generic.
    msg = str(error.message or "").strip()
    return msg[:200]


@lru_cache(maxsize=32)
def load_validator(schema_version: str) -> XsdValidator:
    """Load (and cache) the validator for a supported ISO version identifier."""
    schema_path = _SCHEMA_ROOT / schema_version / f"{schema_version}.xsd"
    if not schema_path.exists():
        raise FileNotFoundError(f"Bundled schema not found for {schema_version}")
    return XsdValidator(schema_path)


def validate_message(root: etree._Element, version_identifier: str) -> SchemaValidationResult:
    """Validate a securely-parsed document against its version-specific bundled schema."""
    validator = load_validator(version_identifier)
    return validator.validate(root)


def validate_pacs008(root: etree._Element, version: SupportedVersion) -> SchemaValidationResult:
    return validate_message(root, version.identifier)
