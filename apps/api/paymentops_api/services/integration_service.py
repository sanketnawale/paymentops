"""Integration profile service: CRUD, versioning, validation, test, publish.

Publishing creates an immutable ``IntegrationProfileVersion`` snapshot and flips the profile
status to PUBLISHED inside a transaction. A published profile is never silently mutated.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

from paymentops_api.db.models import IntegrationProfile as IntegrationProfileRow
from paymentops_api.db.models import IntegrationProfileVersion as VersionRow
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from integration_profiles.models import (
    InputFormat,
    IntegrationProfile,
    ProfileStatus,
)
from mapping_engine.models import MappingDefinition
from mapping_engine.validator import validate_mapping
from rules_engine.declarative import RuleConfig, validate_rule_config


def _to_domain(row: IntegrationProfileRow) -> IntegrationProfile:
    mapping = MappingDefinition.model_validate(row.mapping)
    rules = [RuleConfig.from_dict(r) for r in (row.rules or [])]
    return IntegrationProfile(
        id=str(row.id),
        organization_id=str(row.organization_id),
        name=row.name,
        description=row.description,
        status=ProfileStatus(row.status),
        input_format=InputFormat(row.input_format),
        output_format=row.output_format,
        retention_policy=row.retention_policy,
        address_policy=row.address_policy,
        ai_policy=row.ai_policy,
        allowed_messages=row.allowed_messages or [],
        mapping=mapping,
        rules=rules,
        version_number=row.version_number,
        created_at=row.created_at,
        updated_at=row.updated_at,
        published_at=row.published_at,
    )


async def create_profile(
    session: AsyncSession, organization_id: str, profile: IntegrationProfile
) -> IntegrationProfile:
    row = IntegrationProfileRow(
        organization_id=organization_id,
        name=profile.name,
        description=profile.description,
        status=profile.status.value,
        input_format=profile.input_format.value,
        output_format=profile.output_format.value,
        retention_policy=profile.retention_policy.value,
        address_policy=profile.address_policy,
        ai_policy=profile.ai_policy,
        allowed_messages=profile.allowed_messages or [],
        mapping=profile.mapping.model_dump(),
        rules=[asdict(r) for r in profile.rules],
        version_number=profile.version_number,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _to_domain(row)


async def get_profile(
    session: AsyncSession, organization_id: str, profile_id: str
) -> IntegrationProfile:
    row = await _get_row(session, organization_id, profile_id)
    return _to_domain(row)


async def update_profile(
    session: AsyncSession, organization_id: str, profile_id: str, profile: IntegrationProfile
) -> IntegrationProfile:
    row = await _get_row(session, organization_id, profile_id)
    if row.status == "PUBLISHED":
        raise ValueError("published profiles are immutable; create a new draft version")
    row.name = profile.name
    row.description = profile.description
    row.input_format = profile.input_format.value
    row.output_format = profile.output_format.value
    row.retention_policy = profile.retention_policy.value
    row.address_policy = profile.address_policy
    row.ai_policy = profile.ai_policy
    row.allowed_messages = profile.allowed_messages or []
    row.mapping = profile.mapping.model_dump()
    row.rules = [asdict(r) for r in profile.rules]
    row.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(row)
    return _to_domain(row)


async def publish_profile(
    session: AsyncSession, organization_id: str, profile_id: str
) -> IntegrationProfile:
    """Validate, snapshot an immutable version, and publish (transactional)."""
    row = await _get_row(session, organization_id, profile_id)
    profile = _to_domain(row)

    errors = validate_profile(profile)
    if errors:
        raise ValueError("; ".join(errors))

    # Immutable snapshot.
    version_row = VersionRow(
        profile_id=row.id,
        organization_id=row.organization_id,
        version_number=row.version_number,
        name=row.name,
        input_format=row.input_format,
        mapping=row.mapping,
        rules=row.rules or [],
        mapping_version=profile.mapping_version,
        ruleset_version=profile.ruleset_version,
        published_at=datetime.now(UTC),
    )
    session.add(version_row)
    row.status = "PUBLISHED"
    row.published_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(row)
    return _to_domain(row)


async def list_profile_versions(
    session: AsyncSession, organization_id: str, profile_id: str
) -> list[dict[str, object]]:
    result = await session.execute(
        select(VersionRow)
        .where(VersionRow.profile_id == profile_id, VersionRow.organization_id == organization_id)
        .order_by(VersionRow.version_number.desc())
    )
    return [
        {
            "version_number": v.version_number,
            "name": v.name,
            "input_format": v.input_format,
            "mapping_version": v.mapping_version,
            "ruleset_version": v.ruleset_version,
            "published_at": v.published_at.isoformat(),
        }
        for v in result.scalars().all()
    ]


def validate_profile(profile: IntegrationProfile) -> list[str]:
    errors: list[str] = []
    mv = validate_mapping(profile.mapping)
    errors.extend(f"mapping: {e.code} {e.message}" for e in mv.errors)
    for rc in profile.rules:
        errors.extend(f"rule {rc.rule_id}: {e}" for e in validate_rule_config(rc))
    return errors


async def _get_row(
    session: AsyncSession, organization_id: str, profile_id: str
) -> IntegrationProfileRow:
    result = await session.execute(
        select(IntegrationProfileRow).where(
            IntegrationProfileRow.id == profile_id,
            IntegrationProfileRow.organization_id == organization_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise LookupError("profile not found")
    return row
