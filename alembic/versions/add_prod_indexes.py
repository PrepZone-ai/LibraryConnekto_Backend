"""Add production indexes for performance

Revision ID: add_prod_indexes
Revises: 12089a17ee7e
Create Date: 2026-02-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "add_prod_indexes"
down_revision = "12089a17ee7e"
branch_labels = None
depends_on = None


def upgrade():
    # StudentAttendance indexes
    op.create_index(
        "ix_student_attendance_admin_entry",
        "student_attendance",
        ["admin_id", "entry_time"],
        unique=False,
    )
    op.create_index(
        "ix_student_attendance_student_entry",
        "student_attendance",
        ["student_id", "entry_time"],
        unique=False,
    )
    op.create_index(
        "ix_student_attendance_exit_time",
        "student_attendance",
        ["exit_time"],
        unique=False,
        postgresql_where=sa.text("exit_time IS NULL"),
    )

    # SeatBooking indexes
    op.create_index(
        "ix_seat_booking_admin_status",
        "seat_bookings",
        ["admin_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_seat_booking_payment_status",
        "seat_bookings",
        ["admin_id", "payment_status", "payment_date"],
        unique=False,
    )
    op.create_index(
        "ix_seat_booking_student",
        "seat_bookings",
        ["student_id", "created_at"],
        unique=False,
    )

    # StudentMessage indexes
    op.create_index(
        "ix_student_message_admin_created",
        "student_messages",
        ["admin_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_student_message_student_created",
        "student_messages",
        ["student_id", "created_at"],
        unique=False,
    )

    # Student indexes
    op.create_index(
        "ix_student_admin_active",
        "students",
        ["admin_id", "is_active"],
        unique=False,
    )

    # SubscriptionPlan indexes
    op.create_index(
        "ix_subscription_plan_library",
        "subscription_plans",
        ["library_id", "is_active"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_student_attendance_admin_entry", table_name="student_attendance")
    op.drop_index("ix_student_attendance_student_entry", table_name="student_attendance")
    op.drop_index("ix_student_attendance_exit_time", table_name="student_attendance")
    op.drop_index("ix_seat_booking_admin_status", table_name="seat_bookings")
    op.drop_index("ix_seat_booking_payment_status", table_name="seat_bookings")
    op.drop_index("ix_seat_booking_student", table_name="seat_bookings")
    op.drop_index("ix_student_message_admin_created", table_name="student_messages")
    op.drop_index("ix_student_message_student_created", table_name="student_messages")
    op.drop_index("ix_student_admin_active", table_name="students")
    op.drop_index("ix_subscription_plan_library", table_name="subscription_plans")

