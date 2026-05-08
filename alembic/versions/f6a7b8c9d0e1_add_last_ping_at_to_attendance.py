"""Add last_ping_at to student_attendance

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-05 12:35:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "student_attendance",
        sa.Column("last_ping_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_student_attendance_last_ping_at",
        "student_attendance",
        ["last_ping_at"],
        unique=False,
        postgresql_where=sa.text("exit_time IS NULL"),
    )


def downgrade():
    op.drop_index("ix_student_attendance_last_ping_at", table_name="student_attendance")
    op.drop_column("student_attendance", "last_ping_at")
