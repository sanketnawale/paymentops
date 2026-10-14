"""Analysis persistence tables: cases, runs, findings, candidates, audit.

Revision ID: 0002_analysis
Revises: 0001_platform
Create Date: 2026-09-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_analysis"
down_revision = "0001_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("message_type", sa.String(length=64), nullable=True),
        sa.Column("message_version", sa.String(length=64), nullable=True),
        sa.Column("validation_status", sa.String(length=32), nullable=True),
        sa.Column("address_readiness", sa.String(length=32), nullable=True),
        sa.Column("repair_status", sa.String(length=32), nullable=True),
        sa.Column("ruleset_version", sa.String(length=64), nullable=True),
        sa.Column("address_provider", sa.String(length=64), nullable=True),
        sa.Column("address_provider_version", sa.String(length=64), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("output_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id"),
    )
    op.create_index(op.f("ix_payment_cases_case_id"), "payment_cases", ["case_id"], unique=False)

    op.create_table(
        "analysis_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_analysis_runs_case_id"), "analysis_runs", ["case_id"], unique=False)

    op.create_table(
        "rule_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("rule_id", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("target", sa.String(length=256), nullable=True),
        sa.Column("message", sa.String(length=256), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rule_findings_case_id"), "rule_findings", ["case_id"], unique=False)

    op.create_table(
        "repair_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("candidate_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("xml_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_repair_candidates_case_id"), "repair_candidates", ["case_id"], unique=False
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_events_case_id"), "audit_events", ["case_id"], unique=False)


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("repair_candidates")
    op.drop_table("rule_findings")
    op.drop_table("analysis_runs")
    op.drop_index(op.f("ix_payment_cases_case_id"), table_name="payment_cases")
    op.drop_table("payment_cases")
