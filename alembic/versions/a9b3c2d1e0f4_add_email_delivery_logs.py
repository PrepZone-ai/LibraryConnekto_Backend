"""add email delivery logs

Revision ID: a9b3c2d1e0f4
Revises: add_prod_indexes, 44c61333c264
Create Date: 2026-04-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a9b3c2d1e0f4"
down_revision = ("add_prod_indexes", "44c61333c264")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_delivery_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email_type", sa.String(), nullable=False),
        sa.Column("to_email", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False, server_default="smtp"),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("message_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_delivery_logs_email_type"), "email_delivery_logs", ["email_type"], unique=False)
    op.create_index(op.f("ix_email_delivery_logs_status"), "email_delivery_logs", ["status"], unique=False)
    op.create_index(op.f("ix_email_delivery_logs_to_email"), "email_delivery_logs", ["to_email"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_email_delivery_logs_to_email"), table_name="email_delivery_logs")
    op.drop_index(op.f("ix_email_delivery_logs_status"), table_name="email_delivery_logs")
    op.drop_index(op.f("ix_email_delivery_logs_email_type"), table_name="email_delivery_logs")
    op.drop_table("email_delivery_logs")
