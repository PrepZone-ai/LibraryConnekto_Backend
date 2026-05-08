"""merge heads; add razorpay_linked_account_id to admin_details

Revision ID: h7i8j9k0l1m2
Revises: f0a1b2c3d4e5, f6a7b8c9d0e1
Create Date: 2026-05-06

"""
from alembic import op
import sqlalchemy as sa


revision = "h7i8j9k0l1m2"
down_revision = ("f0a1b2c3d4e5", "f6a7b8c9d0e1")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admin_details",
        sa.Column("razorpay_linked_account_id", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("admin_details", "razorpay_linked_account_id")
