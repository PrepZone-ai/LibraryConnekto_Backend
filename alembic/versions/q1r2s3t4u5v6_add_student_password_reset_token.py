"""Add password_reset_token to students table

Revision ID: q1r2s3t4u5v6
Revises: p8q9r0s1t2u3
Create Date: 2026-05-10

The Student model defines password_reset_token but no migration was ever
created for it. This migration adds the column idempotently so that both
fresh databases and existing ones are handled correctly.
"""

from alembic import op
import sqlalchemy as sa


revision = "q1r2s3t4u5v6"
down_revision = "p8q9r0s1t2u3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='students' AND column_name='password_reset_token'"
        )
    ).scalar()
    if not exists:
        op.add_column("students", sa.Column("password_reset_token", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("students", "password_reset_token")
