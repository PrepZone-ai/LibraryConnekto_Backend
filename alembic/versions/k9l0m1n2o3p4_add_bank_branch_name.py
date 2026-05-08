"""add bank branch name to admin details

Revision ID: k9l0m1n2o3p4
Revises: j8k9l0m1n2o3
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa


revision = "k9l0m1n2o3p4"
down_revision = "j8k9l0m1n2o3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("admin_details", sa.Column("bank_branch_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("admin_details", "bank_branch_name")
