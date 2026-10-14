"""Week 6: account reports, entries, balances, reconciliations + lifecycle account context.

Revision ID: 0008_account
Revises: 0007_profile_allowed_messages
Create Date: 2026-09-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_account"
down_revision = "0007_profile_allowed_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payment_lifecycles", sa.Column("debtor_account", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "payment_lifecycles", sa.Column("creditor_account", sa.String(length=64), nullable=True)
    )

    op.create_table(
        "account_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("iso_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("message_id", sa.String(length=128), nullable=True),
        sa.Column("message_definition", sa.String(length=64), nullable=False),
        sa.Column("message_version", sa.String(length=32), nullable=False),
        sa.Column("report_type", sa.String(length=16), nullable=False),
        sa.Column("account_iban", sa.String(length=64), nullable=True),
        sa.Column("account_other_id", sa.String(length=64), nullable=True),
        sa.Column("account_currency", sa.String(length=3), nullable=True),
        sa.Column("servicer_bic", sa.String(length=11), nullable=True),
        sa.Column("statement_id", sa.String(length=64), nullable=True),
        sa.Column("notification_id", sa.String(length=64), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["iso_message_id"], ["iso_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_reports_organization_id", "account_reports", ["organization_id"])
    op.create_index("ix_account_reports_iso_message_id", "account_reports", ["iso_message_id"])
    op.create_index("ix_account_reports_account_iban", "account_reports", ["account_iban"])

    op.create_table(
        "account_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_reference", sa.String(length=64), nullable=True),
        sa.Column("account_servicer_reference", sa.String(length=64), nullable=True),
        sa.Column("transaction_id", sa.String(length=128), nullable=True),
        sa.Column("instruction_id", sa.String(length=128), nullable=True),
        sa.Column("end_to_end_id", sa.String(length=128), nullable=True),
        sa.Column("uetr", sa.String(length=64), nullable=True),
        sa.Column("amount_minor", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("credit_debit", sa.String(length=4), nullable=True),
        sa.Column("booking_date", sa.Date(), nullable=True),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=True),
        sa.Column("bank_tx_code", sa.String(length=8), nullable=True),
        sa.Column("bank_tx_family", sa.String(length=8), nullable=True),
        sa.Column("bank_tx_sub_family", sa.String(length=8), nullable=True),
        sa.Column("remittance_reference", sa.String(length=256), nullable=True),
        sa.Column("identity_hash", sa.String(length=64), nullable=False),
        sa.Column("reconciliation_status", sa.String(length=32), nullable=True),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("lifecycle_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("conflicts", postgresql.JSONB(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["account_reports.id"]),
        sa.ForeignKeyConstraint(["lifecycle_id"], ["payment_lifecycles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_entries_organization_id", "account_entries", ["organization_id"])
    op.create_index("ix_account_entries_report_id", "account_entries", ["report_id"])
    op.create_index("ix_account_entries_identity_hash", "account_entries", ["identity_hash"])
    op.create_index(
        "ix_account_entries_reconciliation_status", "account_entries", ["reconciliation_status"]
    )
    op.create_index("ix_account_entries_lifecycle_id", "account_entries", ["lifecycle_id"])

    op.create_table(
        "account_balances",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("balance_type", sa.String(length=8), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("credit_debit", sa.String(length=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["account_reports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_balances_organization_id", "account_balances", ["organization_id"])
    op.create_index("ix_account_balances_report_id", "account_balances", ["report_id"])

    op.create_table(
        "account_reconciliations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lifecycle_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("conflicts", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("operator", sa.String(length=128), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["account_entry_id"], ["account_entries.id"]),
        sa.ForeignKeyConstraint(["lifecycle_id"], ["payment_lifecycles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_account_reconciliations_organization_id", "account_reconciliations", ["organization_id"]
    )
    op.create_index(
        "ix_account_reconciliations_account_entry_id",
        "account_reconciliations",
        ["account_entry_id"],
    )
    op.create_index(
        "ix_account_reconciliations_lifecycle_id", "account_reconciliations", ["lifecycle_id"]
    )
    op.create_index(
        "ix_account_reconciliations_classification", "account_reconciliations", ["classification"]
    )


def downgrade() -> None:
    op.drop_table("account_reconciliations")
    op.drop_table("account_balances")
    op.drop_table("account_entries")
    op.drop_table("account_reports")
    op.drop_column("payment_lifecycles", "creditor_account")
    op.drop_column("payment_lifecycles", "debtor_account")
