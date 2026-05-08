"""add admin password_reset_token

Revision ID: b7e8f9a1c2d3
Revises: a9b3c2d1e0f4
Create Date: 2026-05-04

"""
from alembic import op
import sqlalchemy as sa


revision = "b7e8f9a1c2d3"
down_revision = "a9b3c2d1e0f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admin_users",
        sa.Column("password_reset_token", sa.String(), nullable=True),
    )
    op.create_index(
        op.f("ix_admin_users_password_reset_token"),
        "admin_users",
        ["password_reset_token"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_admin_users_password_reset_token"), table_name="admin_users")
    op.drop_column("admin_users", "password_reset_token")
