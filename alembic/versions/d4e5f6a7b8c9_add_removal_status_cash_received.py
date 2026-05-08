"""add removal status cash_received

Revision ID: d4e5f6a7b8c9
Revises: c3a4b5d6e7f8
Create Date: 2026-05-05

"""
from alembic import op


revision = "d4e5f6a7b8c9"
down_revision = "c3a4b5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL: extend enum used by student_removal_requests.status
    op.execute("ALTER TYPE removalrequeststatus ADD VALUE IF NOT EXISTS 'cash_received'")


def downgrade() -> None:
    # Postgres cannot drop enum values safely; no-op
    pass
