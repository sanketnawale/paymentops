"""Add allowed_messages to integration profiles (ISO message/version restriction).

Revision ID: 0007_profile_allowed_messages
Revises: 0006_lifecycle
Create Date: 2026-09-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_profile_allowed_messages"
down_revision = "0006_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "integration_profiles",
        sa.Column("allowed_messages", postgresql.JSONB(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("integration_profiles", "allowed_messages")
