"""Align removalrequeststatus cash_received label with SQLAlchemy PG bind (CASH_RECEIVED).

Revision ID: p8q9r0s1t2u3
Revises: c1d2e3f4a5b6
Create Date: 2026-05-10

SQLAlchemy maps Python Enum member names to PostgreSQL enum labels. Migration d4e5f6a7b8c9
added lowercase 'cash_received', while binds send 'CASH_RECEIVED'.

"""

from alembic import op
import sqlalchemy as sa


revision = "p8q9r0s1t2u3"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    has_lower = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid "
            "WHERE t.typname = 'removalrequeststatus' AND e.enumlabel = 'cash_received'"
        )
    ).scalar()
    has_upper = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid "
            "WHERE t.typname = 'removalrequeststatus' AND e.enumlabel = 'CASH_RECEIVED'"
        )
    ).scalar()

    if has_lower and not has_upper:
        op.execute(
            "ALTER TYPE removalrequeststatus RENAME VALUE 'cash_received' TO 'CASH_RECEIVED'"
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    has_upper = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid "
            "WHERE t.typname = 'removalrequeststatus' AND e.enumlabel = 'CASH_RECEIVED'"
        )
    ).scalar()
    has_lower = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid "
            "WHERE t.typname = 'removalrequeststatus' AND e.enumlabel = 'cash_received'"
        )
    ).scalar()

    if has_upper and not has_lower:
        op.execute(
            "ALTER TYPE removalrequeststatus RENAME VALUE 'CASH_RECEIVED' TO 'cash_received'"
        )
