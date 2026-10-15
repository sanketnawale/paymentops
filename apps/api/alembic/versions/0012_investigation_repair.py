"""Phase 2B: sandbox repair state on investigations.

Revision ID: 0012_investigation_repair
Revises: 0011_investigations
Create Date: 2026-10-15

Additive only.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012_investigation_repair"
down_revision = "0011_investigations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "investigations", sa.Column("supporting_record", postgresql.JSONB(), nullable=True)
    )
    op.add_column("investigations", sa.Column("repair", postgresql.JSONB(), nullable=True))
    op.add_column("investigations", sa.Column("answer_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("investigations", "answer_text")
    op.drop_column("investigations", "repair")
    op.drop_column("investigations", "supporting_record")
