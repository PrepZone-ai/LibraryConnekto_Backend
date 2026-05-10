"""add admin bank details fields

Revision ID: j8k9l0m1n2o3
Revises: h7i8j9k0l1m2
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa


revision = "j8k9l0m1n2o3"
down_revision = "h7i8j9k0l1m2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    existing = {
        row[0]
        for row in conn.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='admin_details'"
            )
        )
    }
    for col_name, col_type in [
        ("bank_account_holder_name", sa.String()),
        ("bank_account_number", sa.String()),
        ("bank_ifsc_code", sa.String()),
        ("bank_name", sa.String()),
    ]:
        if col_name not in existing:
            op.add_column("admin_details", sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    op.drop_column("admin_details", "bank_name")
    op.drop_column("admin_details", "bank_ifsc_code")
    op.drop_column("admin_details", "bank_account_number")
    op.drop_column("admin_details", "bank_account_holder_name")
