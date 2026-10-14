"""Week 8: allow audit events without a case (authentication / administration).

Revision ID: 0010_audit_case_nullable
Revises: 0009_users_sessions
Create Date: 2026-09-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_audit_case_nullable"
down_revision = "0009_users_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("audit_events", "case_id", existing_type=sa.String(length=64), nullable=True)


def downgrade() -> None:
    op.alter_column("audit_events", "case_id", existing_type=sa.String(length=64), nullable=False)
