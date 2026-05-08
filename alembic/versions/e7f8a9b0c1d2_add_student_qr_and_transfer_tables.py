"""add student qr and transfer tables

Revision ID: e7f8a9b0c1d2
Revises: d4e5f6a7b8c9
Create Date: 2026-05-05

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e7f8a9b0c1d2"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_qr_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_student_qr_tokens_student_id", "student_qr_tokens", ["student_id"])
    op.create_index("ix_student_qr_tokens_expires_at", "student_qr_tokens", ["expires_at"])
    op.create_index("ix_student_qr_tokens_is_active", "student_qr_tokens", ["is_active"])

    op.create_table(
        "student_transfer_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="initiated"),
        sa.Column("payment_reference", sa.String(), nullable=True),
        sa.Column("payment_link", sa.Text(), nullable=True),
        sa.Column("initiated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["source_admin_id"], ["admin_users.user_id"]),
        sa.ForeignKeyConstraint(["target_admin_id"], ["admin_users.user_id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_student_transfer_requests_student_id", "student_transfer_requests", ["student_id"])
    op.create_index("ix_student_transfer_requests_source_admin_id", "student_transfer_requests", ["source_admin_id"])
    op.create_index("ix_student_transfer_requests_target_admin_id", "student_transfer_requests", ["target_admin_id"])
    op.create_index("ix_student_transfer_requests_status", "student_transfer_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_student_transfer_requests_status", table_name="student_transfer_requests")
    op.drop_index("ix_student_transfer_requests_target_admin_id", table_name="student_transfer_requests")
    op.drop_index("ix_student_transfer_requests_source_admin_id", table_name="student_transfer_requests")
    op.drop_index("ix_student_transfer_requests_student_id", table_name="student_transfer_requests")
    op.drop_table("student_transfer_requests")

    op.drop_index("ix_student_qr_tokens_is_active", table_name="student_qr_tokens")
    op.drop_index("ix_student_qr_tokens_expires_at", table_name="student_qr_tokens")
    op.drop_index("ix_student_qr_tokens_student_id", table_name="student_qr_tokens")
    op.drop_table("student_qr_tokens")
