"""add admin email verification fields

Revision ID: c1d2e3f4a5b6
Revises: k9l0m1n2o3p4
Create Date: 2026-05-09

"""

from alembic import op
import sqlalchemy as sa


revision = "c1d2e3f4a5b6"
down_revision = "k9l0m1n2o3p4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("admin_users", sa.Column("email_verification_token", sa.String(), nullable=True))
    op.add_column(
        "admin_users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        op.f("ix_admin_users_email_verification_token"),
        "admin_users",
        ["email_verification_token"],
        unique=False,
    )

    # Drop the server default after backfilling existing rows.
    op.alter_column("admin_users", "email_verified", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_admin_users_email_verification_token"), table_name="admin_users")
    op.drop_column("admin_users", "email_verified")
    op.drop_column("admin_users", "email_verification_token")

