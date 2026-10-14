"""Week 5: ISO messages, payment lifecycles, lifecycle events, message correlations.

Revision ID: 0006_lifecycle
Revises: 0005_matching
Create Date: 2026-09-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_lifecycle"
down_revision = "0005_matching"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "iso_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", sa.String(length=128), nullable=True),
        sa.Column("message_family", sa.String(length=16), nullable=False),
        sa.Column("message_definition", sa.String(length=64), nullable=False),
        sa.Column("message_version", sa.String(length=32), nullable=False),
        sa.Column("namespace", sa.String(length=128), nullable=False),
        sa.Column("source_adapter", sa.String(length=64), nullable=False),
        sa.Column("adapter_version", sa.String(length=16), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("schema_validation", sa.Boolean(), nullable=False),
        sa.Column("message_hash", sa.String(length=64), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("canonical_model_version", sa.String(length=64), nullable=True),
        sa.Column("engine_version", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("raw_status", sa.String(length=32), nullable=True),
        sa.Column("normalized_status", sa.String(length=32), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_iso_messages_organization_id", "iso_messages", ["organization_id"])
    op.create_index("ix_iso_messages_message_hash", "iso_messages", ["message_hash"])

    op.create_table(
        "payment_lifecycles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lifecycle_id", sa.String(length=64), nullable=False),
        sa.Column("primary_reference", sa.String(length=128), nullable=True),
        sa.Column("end_to_end_id", sa.String(length=128), nullable=True),
        sa.Column("instruction_id", sa.String(length=128), nullable=True),
        sa.Column("transaction_id", sa.String(length=128), nullable=True),
        sa.Column("uetr", sa.String(length=64), nullable=True),
        sa.Column("original_message_id", sa.String(length=128), nullable=True),
        sa.Column("amount_minor", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("current_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_payment_lifecycles_organization_id", "payment_lifecycles", ["organization_id"]
    )
    op.create_index("ix_payment_lifecycles_lifecycle_id", "payment_lifecycles", ["lifecycle_id"])

    op.create_table(
        "payment_lifecycle_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lifecycle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("message_family", sa.String(length=16), nullable=True),
        sa.Column("message_definition", sa.String(length=64), nullable=True),
        sa.Column("message_version", sa.String(length=32), nullable=True),
        sa.Column("message_id", sa.String(length=128), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("raw_status_code", sa.String(length=32), nullable=True),
        sa.Column("reasons", postgresql.JSONB(), nullable=False),
        sa.Column("correlation_evidence", postgresql.JSONB(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["lifecycle_id"], ["payment_lifecycles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_payment_lifecycle_events_organization_id",
        "payment_lifecycle_events",
        ["organization_id"],
    )
    op.create_index(
        "ix_payment_lifecycle_events_lifecycle_id",
        "payment_lifecycle_events",
        ["lifecycle_id"],
    )

    op.create_table(
        "message_correlations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lifecycle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_message_id", sa.String(length=128), nullable=True),
        sa.Column("candidate_message_id", sa.String(length=128), nullable=True),
        sa.Column("correlation_status", sa.String(length=32), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("conflicts", postgresql.JSONB(), nullable=False),
        sa.Column("operator", sa.String(length=128), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["lifecycle_id"], ["payment_lifecycles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_message_correlations_organization_id", "message_correlations", ["organization_id"]
    )
    op.create_index(
        "ix_message_correlations_lifecycle_id", "message_correlations", ["lifecycle_id"]
    )


def downgrade() -> None:
    op.drop_table("message_correlations")
    op.drop_table("payment_lifecycle_events")
    op.drop_table("payment_lifecycles")
    op.drop_table("iso_messages")
