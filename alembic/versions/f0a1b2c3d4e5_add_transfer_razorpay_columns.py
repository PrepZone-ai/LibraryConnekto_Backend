"""add transfer razorpay columns

Revision ID: f0a1b2c3d4e5
Revises: e7f8a9b0c1d2
Create Date: 2026-05-05
"""

from alembic import op
import sqlalchemy as sa


revision = "f0a1b2c3d4e5"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("student_transfer_requests", sa.Column("razorpay_order_id", sa.String(), nullable=True))
    op.add_column("student_transfer_requests", sa.Column("razorpay_payment_id", sa.String(), nullable=True))
    op.add_column("student_transfer_requests", sa.Column("payment_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_student_transfer_requests_razorpay_order_id", "student_transfer_requests", ["razorpay_order_id"])
    op.create_index("ix_student_transfer_requests_razorpay_payment_id", "student_transfer_requests", ["razorpay_payment_id"])


def downgrade() -> None:
    op.drop_index("ix_student_transfer_requests_razorpay_payment_id", table_name="student_transfer_requests")
    op.drop_index("ix_student_transfer_requests_razorpay_order_id", table_name="student_transfer_requests")
    op.drop_column("student_transfer_requests", "payment_verified_at")
    op.drop_column("student_transfer_requests", "razorpay_payment_id")
    op.drop_column("student_transfer_requests", "razorpay_order_id")
