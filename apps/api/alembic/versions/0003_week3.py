"""Week 3: integration profiles, versions, api clients, batch jobs, case actions, tenant scoping.

Revision ID: 0003_week3
Revises: 0002_analysis
Create Date: 2026-09-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_week3"
down_revision = "0002_analysis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Tenant + version columns on existing tables ---
    op.add_column(
        "payment_cases", sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "payment_cases", sa.Column("mapping_version", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "payment_cases",
        sa.Column("integration_profile_version", sa.String(length=64), nullable=True),
    )
    op.add_column("payment_cases", sa.Column("engine_version", sa.String(length=64), nullable=True))
    op.add_column(
        "payment_cases", sa.Column("address_provider_coverage", sa.String(length=32), nullable=True)
    )
    op.add_column(
        "payment_cases",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="NEW"),
    )
    op.add_column(
        "payment_cases", sa.Column("idempotency_key", sa.String(length=128), nullable=True)
    )
    op.create_index("ix_payment_cases_organization_id", "payment_cases", ["organization_id"])
    op.create_index("ix_payment_cases_idempotency_key", "payment_cases", ["idempotency_key"])

    op.add_column(
        "analysis_runs", sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_index("ix_analysis_runs_organization_id", "analysis_runs", ["organization_id"])
    op.add_column(
        "rule_findings", sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_index("ix_rule_findings_organization_id", "rule_findings", ["organization_id"])
    op.add_column(
        "repair_candidates",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_repair_candidates_organization_id", "repair_candidates", ["organization_id"]
    )

    op.add_column(
        "audit_events", sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column("audit_events", sa.Column("profile_id", sa.String(length=64), nullable=True))
    op.add_column("audit_events", sa.Column("profile_version", sa.String(length=64), nullable=True))
    op.add_column("audit_events", sa.Column("mapping_version", sa.String(length=64), nullable=True))
    op.add_column("audit_events", sa.Column("ruleset_version", sa.String(length=64), nullable=True))
    op.add_column("audit_events", sa.Column("event_type", sa.String(length=64), nullable=True))
    op.add_column("audit_events", sa.Column("user_identity", sa.String(length=128), nullable=True))
    op.add_column("audit_events", sa.Column("input_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_events", sa.Column("output_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_events", sa.Column("action_metadata", postgresql.JSONB(), nullable=True))
    op.create_index("ix_audit_events_organization_id", "audit_events", ["organization_id"])

    # --- New tables ---
    op.create_table(
        "integration_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_format", sa.String(length=32), nullable=False),
        sa.Column("output_format", sa.String(length=32), nullable=False),
        sa.Column("retention_policy", sa.String(length=32), nullable=False),
        sa.Column("address_policy", sa.String(length=32), nullable=False),
        sa.Column("ai_policy", sa.String(length=32), nullable=False),
        sa.Column("mapping", postgresql.JSONB(), nullable=False),
        sa.Column("rules", postgresql.JSONB(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_integration_profiles_organization_id", "integration_profiles", ["organization_id"]
    )

    op.create_table(
        "integration_profile_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("input_format", sa.String(length=32), nullable=False),
        sa.Column("mapping", postgresql.JSONB(), nullable=False),
        sa.Column("rules", postgresql.JSONB(), nullable=False),
        sa.Column("mapping_version", sa.String(length=64), nullable=False),
        sa.Column("ruleset_version", sa.String(length=64), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["integration_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_integration_profile_versions_profile_id", "integration_profile_versions", ["profile_id"]
    )
    op.create_index(
        "ix_integration_profile_versions_organization_id",
        "integration_profile_versions",
        ["organization_id"],
    )

    op.create_table(
        "api_clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("secret_hash", sa.String(length=256), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("allowed_profiles", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id"),
    )
    op.create_index("ix_api_clients_organization_id", "api_clients", ["organization_id"])

    op.create_table(
        "batch_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_records", sa.Integer(), nullable=False),
        sa.Column("processed_records", sa.Integer(), nullable=False),
        sa.Column("ready_count", sa.Integer(), nullable=False),
        sa.Column("repairable_count", sa.Integer(), nullable=False),
        sa.Column("review_required_count", sa.Integer(), nullable=False),
        sa.Column("unresolved_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("report", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_batch_jobs_organization_id", "batch_jobs", ["organization_id"])

    op.create_table(
        "case_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("operator", sa.String(length=128), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_case_actions_organization_id", "case_actions", ["organization_id"])
    op.create_index("ix_case_actions_case_id", "case_actions", ["case_id"])


def downgrade() -> None:
    op.drop_table("case_actions")
    op.drop_table("batch_jobs")
    op.drop_table("api_clients")
    op.drop_table("integration_profile_versions")
    op.drop_table("integration_profiles")
    op.drop_column("audit_events", "action_metadata")
    op.drop_column("audit_events", "output_hash")
    op.drop_column("audit_events", "input_hash")
    op.drop_column("audit_events", "user_identity")
    op.drop_column("audit_events", "event_type")
    op.drop_column("audit_events", "ruleset_version")
    op.drop_column("audit_events", "mapping_version")
    op.drop_column("audit_events", "profile_version")
    op.drop_column("audit_events", "profile_id")
    op.drop_index("ix_audit_events_organization_id", table_name="audit_events")
    op.drop_column("audit_events", "organization_id")
    op.drop_column("repair_candidates", "organization_id")
    op.drop_column("rule_findings", "organization_id")
    op.drop_column("analysis_runs", "organization_id")
    op.drop_index("ix_payment_cases_idempotency_key", table_name="payment_cases")
    op.drop_column("payment_cases", "idempotency_key")
    op.drop_column("payment_cases", "status")
    op.drop_column("payment_cases", "address_provider_coverage")
    op.drop_column("payment_cases", "engine_version")
    op.drop_column("payment_cases", "integration_profile_version")
    op.drop_column("payment_cases", "mapping_version")
    op.drop_index("ix_payment_cases_organization_id", table_name="payment_cases")
    op.drop_column("payment_cases", "organization_id")
