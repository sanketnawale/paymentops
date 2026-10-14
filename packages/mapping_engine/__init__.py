"""CloudNova mapping engine.

Declarative, data-driven mapping from customer input (JSON / custom XML / CSV) into the
canonical :class:`PaymentMessage`. No arbitrary code execution; controlled selectors and a
safe, versioned transform library.
"""

from __future__ import annotations

from mapping_engine.mapper import map_to_canonical
from mapping_engine.models import (
    FieldMapping,
    FieldRequirement,
    MappingDefinition,
    MappingIssue,
    MappingResult,
    MappingSeverity,
    SourceFormat,
)
from mapping_engine.transforms import supported_transforms
from mapping_engine.validator import MappingValidation, validate_mapping

__all__ = [
    "FieldMapping",
    "FieldRequirement",
    "MappingDefinition",
    "MappingIssue",
    "MappingResult",
    "MappingSeverity",
    "MappingValidation",
    "SourceFormat",
    "map_to_canonical",
    "supported_transforms",
    "validate_mapping",
]
