"""Week 4: matching records, policies, runs, and candidates.

Revision ID: 0005_matching
Revises: 0004_audit_event_fix
Create Date: 2026-09-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_matching"
down_revision = "0004_audit_event_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "match_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_id", sa.String(length=128), nullable=False),
        sa.Column("record_type", sa.String(length=32), nullable=False),
        sa.Column("profile_id", sa.String(length=64), nullable=True),
        sa.Column("source_system", sa.String(length=64), nullable=True),
        sa.Column("message_type", sa.String(length=64), nullable=True),
        sa.Column("instruction_id", sa.String(length=128), nullable=True),
        sa.Column("end_to_end_id", sa.String(length=128), nullable=True),
        sa.Column("transaction_id", sa.String(length=128), nullable=True),
        sa.Column("amount", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("booking_date", sa.Date(), nullable=True),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("debtor_name", sa.String(length=256), nullable=True),
        sa.Column("creditor_name", sa.String(length=256), nullable=True),
        sa.Column("debtor_account", sa.String(length=128), nullable=True),
        sa.Column("creditor_account", sa.String(length=128), nullable=True),
        sa.Column("debtor_agent", sa.String(length=64), nullable=True),
        sa.Column("creditor_agent", sa.String(length=64), nullable=True),
        sa.Column("remittance_reference", sa.String(length=256), nullable=True),
        sa.Column("external_reference", sa.String(length=256), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("source_hash", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_match_records_organization_id", "match_records", ["organization_id"])
    op.create_index("ix_match_records_record_id", "match_records", ["record_id"])
    op.create_index(
        "ix_match_records_org_type", "match_records", ["organization_id", "record_type"]
    )

    op.create_table(
        "matching_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_matching_policies_organization_id", "matching_policies", ["organization_id"]
    )

    op.create_table(
        "matching_policy_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("field_weights", postgresql.JSONB(), nullable=False),
        sa.Column("thresholds", postgresql.JSONB(), nullable=False),
        sa.Column("date_tolerances", postgresql.JSONB(), nullable=False),
        sa.Column("amount_tolerances", postgresql.JSONB(), nullable=False),
        sa.Column("critical_fields", postgresql.JSONB(), nullable=False),
        sa.Column("fuzzy_algorithms", postgresql.JSONB(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["policy_id"], ["matching_policies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_matching_policy_versions_policy_id",
        "matching_policy_versions",
        ["policy_id"],
    )
    op.create_index(
        "ix_matching_policy_versions_organization_id",
        "matching_policy_versions",
        ["organization_id"],
    )

    op.create_table(
        "match_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("policy_version", sa.String(length=64), nullable=True),
        sa.Column("source_dataset", postgresql.JSONB(), nullable=False),
        sa.Column("candidate_dataset", postgresql.JSONB(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("matched", sa.Integer(), nullable=False),
        sa.Column("possible_match", sa.Integer(), nullable=False),
        sa.Column("review_required", sa.Integer(), nullable=False),
        sa.Column("unmatched", sa.Integer(), nullable=False),
        sa.Column("duplicate_candidate", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("report", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_match_runs_organization_id", "match_runs", ["organization_id"])

    op.create_table(
        "match_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_record_id", sa.String(length=128), nullable=False),
        sa.Column("candidate_record_id", sa.String(length=128), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("critical_conflicts", postgresql.JSONB(), nullable=False),
        sa.Column("field_results", postgresql.JSONB(), nullable=False),
        sa.Column("explanation_codes", postgresql.JSONB(), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=True),
        sa.Column("engine_version", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("operator", sa.String(length=128), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["match_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_match_candidates_organization_id", "match_candidates", ["organization_id"])
    op.create_index("ix_match_candidates_run_id", "match_candidates", ["run_id"])
    op.create_index(
        "ix_match_candidates_source_record_id", "match_candidates", ["source_record_id"]
    )


def downgrade() -> None:
    op.drop_table("match_candidates")
    op.drop_table("match_runs")
    op.drop_table("matching_policy_versions")
    op.drop_table("matching_policies")
    op.drop_table("match_records")
