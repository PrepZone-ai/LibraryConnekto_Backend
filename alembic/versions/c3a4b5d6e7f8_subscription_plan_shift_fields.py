"""subscription_plan_shift_fields

Revision ID: c3a4b5d6e7f8
Revises: b7e8f9a1c2d3
Create Date: 2026-05-04

"""
from alembic import op
import sqlalchemy as sa


revision = "c3a4b5d6e7f8"
down_revision = "b7e8f9a1c2d3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "subscription_plans",
        sa.Column("is_shift_plan", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("subscription_plans", sa.Column("shift_time", sa.String(), nullable=True))
    op.create_index(
        "ix_subscription_plans_library_shift",
        "subscription_plans",
        ["library_id", "is_shift_plan", "shift_time"],
        unique=False,
    )
    op.alter_column("subscription_plans", "is_shift_plan", server_default=None)


def downgrade():
    op.drop_index("ix_subscription_plans_library_shift", table_name="subscription_plans")
    op.drop_column("subscription_plans", "shift_time")
    op.drop_column("subscription_plans", "is_shift_plan")
