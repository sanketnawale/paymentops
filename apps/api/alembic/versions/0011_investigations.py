"""Phase 1: investigations (Evolus / AMD-powered investigator).

Revision ID: 0011_investigations
Revises: 0010_audit_case_nullable
Create Date: 2026-10-14

Additive only. Does not touch any existing table.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011_investigations"
down_revision = "0010_audit_case_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investigations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("investigation_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("demo_case_key", sa.String(length=64), nullable=False),
        sa.Column("message_version", sa.String(length=64), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("ruleset_version", sa.String(length=64), nullable=True),
        sa.Column("engine_version", sa.String(length=64), nullable=True),
        sa.Column("profile_version", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("evolus_execution_id", sa.String(length=128), nullable=True),
        sa.Column("evolus_trace_id", sa.String(length=128), nullable=True),
        sa.Column("deterministic_findings", postgresql.JSONB(), nullable=True),
        sa.Column("agent_result", postgresql.JSONB(), nullable=True),
        sa.Column("agent_status", sa.String(length=32), nullable=True),
        sa.Column("error", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("investigation_id"),
    )
    op.create_index("ix_investigations_investigation_id", "investigations", ["investigation_id"])
    op.create_index("ix_investigations_organization_id", "investigations", ["organization_id"])
    op.create_index(
        "ix_investigations_evolus_execution_id", "investigations", ["evolus_execution_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_investigations_evolus_execution_id", table_name="investigations")
    op.drop_index("ix_investigations_organization_id", table_name="investigations")
    op.drop_index("ix_investigations_investigation_id", table_name="investigations")
    op.drop_table("investigations")
