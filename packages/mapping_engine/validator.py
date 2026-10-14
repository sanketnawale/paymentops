"""Mapping definition validation (before a profile can be published)."""

from __future__ import annotations

from dataclasses import dataclass, field

from mapping_engine.models import MappingDefinition, MappingIssue, MappingSeverity
from mapping_engine.transforms import supported_transforms

# Allowed canonical target paths (relative to a transaction).
_ALLOWED_TARGETS = {
    "instruction_id",
    "end_to_end_id",
    "transaction_id",
    "amount.amount_minor",
    "amount.currency",
    "debtor.name",
    "creditor.name",
    "debtor.postal_address.street_name",
    "debtor.postal_address.building_number",
    "debtor.postal_address.postcode",
    "debtor.postal_address.town_name",
    "debtor.postal_address.country",
    "debtor.postal_address.address_lines",
    "creditor.postal_address.street_name",
    "creditor.postal_address.building_number",
    "creditor.postal_address.postcode",
    "creditor.postal_address.town_name",
    "creditor.postal_address.country",
    "creditor.postal_address.address_lines",
    "debtor_account.iban",
    "debtor_account.name",
    "debtor_account.other_identification",
    "creditor_account.iban",
    "creditor_account.name",
    "debtor_agent.bic",
    "debtor_agent.name",
    "creditor_agent.bic",
    "creditor_agent.name",
    "remittance.unstructured",
}

_TRANSFORMS = set(supported_transforms())


@dataclass
class MappingValidation:
    valid: bool
    errors: list[MappingIssue] = field(default_factory=list)
    warnings: list[MappingIssue] = field(default_factory=list)


def validate_mapping(definition: MappingDefinition) -> MappingValidation:
    errors: list[MappingIssue] = []
    warnings: list[MappingIssue] = []
    seen_targets: set[str] = set()

    if not definition.fields:
        errors.append(
            MappingIssue("MAP-002", MappingSeverity.ERROR, "Mapping has no field mappings")
        )
    if definition.source_format.value == "json" and not definition.record_selector:
        warnings.append(
            MappingIssue("MAP-010", MappingSeverity.WARNING, "JSON mapping lacks record_selector")
        )
    if definition.source_format.value == "custom_xml" and not definition.record_selector:
        errors.append(
            MappingIssue(
                "MAP-011", MappingSeverity.ERROR, "Custom XML mapping requires record_selector"
            )
        )

    for fm in definition.fields:
        if not fm.source:
            errors.append(
                MappingIssue("MAP-003", MappingSeverity.ERROR, "Empty source selector", fm.target)
            )
        if fm.target not in _ALLOWED_TARGETS:
            errors.append(
                MappingIssue(
                    "MAP-004",
                    MappingSeverity.ERROR,
                    f"Unknown canonical target '{fm.target}'",
                    fm.target,
                )
            )
        if fm.target in seen_targets:
            errors.append(
                MappingIssue(
                    "MAP-005", MappingSeverity.ERROR, f"Duplicate target '{fm.target}'", fm.target
                )
            )
        seen_targets.add(fm.target)
        for t in fm.transforms:
            if t not in _TRANSFORMS:
                errors.append(
                    MappingIssue(
                        "MAP-006", MappingSeverity.ERROR, f"Unsupported transform '{t}'", fm.target
                    )
                )

    # Simple type-compatibility check for amount/currency.
    for fm in definition.fields:
        if fm.target == "amount.currency" and any(t in ("parse_decimal",) for t in fm.transforms):
            warnings.append(
                MappingIssue(
                    "MAP-007",
                    MappingSeverity.WARNING,
                    "currency should not be decimal-parsed",
                    fm.target,
                )
            )

    return MappingValidation(valid=not errors, errors=errors, warnings=warnings)
