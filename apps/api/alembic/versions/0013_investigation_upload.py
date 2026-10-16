"""Phase 2C: uploaded synthetic cases on investigations.

Revision ID: 0013_investigation_upload
Revises: 0012_investigation_repair
Create Date: 2026-10-15

Additive only.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013_investigation_upload"
down_revision = "0012_investigation_repair"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "investigations",
        sa.Column("source", sa.String(length=16), nullable=False, server_default="demo"),
    )
    op.add_column("investigations", sa.Column("payload_xml", sa.Text(), nullable=True))
    op.add_column(
        "investigations", sa.Column("payload_evidence", postgresql.JSONB(), nullable=True)
    )
    op.add_column("investigations", sa.Column("evidence_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("investigations", "evidence_hash")
    op.drop_column("investigations", "payload_evidence")
    op.drop_column("investigations", "payload_xml")
    op.drop_column("investigations", "source")
