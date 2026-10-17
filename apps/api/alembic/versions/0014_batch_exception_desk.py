"""Phase 3A: bounded Batch Exception Desk persistence.

Revision ID: 0014_batch_exception_desk
Revises: 0013_investigation_upload
Create Date: 2026-10-17

Additive only.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014_batch_exception_desk"
down_revision = "0013_investigation_upload"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "batch_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", sa.String(length=64), nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_batch_run_org_idem"),
    )
    op.create_index("ix_batch_runs_batch_id", "batch_runs", ["batch_id"], unique=True)
    op.create_index("ix_batch_runs_organization_id", "batch_runs", ["organization_id"])

    op.create_table(
        "batch_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("item_id", sa.String(length=64), nullable=False),
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("batch_runs.id"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("item_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("display_filename", sa.String(length=255), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=True),
        sa.Column("payload_xml", sa.Text(), nullable=True),
        sa.Column("payload_evidence", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("investigation_id", sa.String(length=64), nullable=True),
        sa.Column("evolus_execution_id", sa.String(length=128), nullable=True),
        sa.Column("error", sa.String(length=512), nullable=True),
        sa.Column("claimed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_batch_items_item_id", "batch_items", ["item_id"], unique=True)
    op.create_index("ix_batch_items_batch_id", "batch_items", ["batch_id"])
    op.create_index("ix_batch_items_organization_id", "batch_items", ["organization_id"])
    op.create_index("ix_batch_items_investigation_id", "batch_items", ["investigation_id"])


def downgrade() -> None:
    op.drop_table("batch_items")
    op.drop_table("batch_runs")
