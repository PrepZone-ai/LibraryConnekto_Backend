"""add_payment_fields_to_bookings

Revision ID: 32465a9065a8
Revises: 9da141b0fd47
Create Date: 2025-09-20 01:36:13.974238

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '32465a9065a8'
down_revision = '9da141b0fd47'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Columns seat_id, subscription_plan_id, date, start_time, end_time,
    # purpose and the FK on subscription_plan_id are already added by the
    # previous revision (9da141b0fd47). Only the payment_* columns are new.
    op.add_column('seat_bookings', sa.Column('payment_status', sa.String(), nullable=True))
    op.add_column('seat_bookings', sa.Column('payment_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('seat_bookings', sa.Column('payment_method', sa.String(), nullable=True))
    op.add_column('seat_bookings', sa.Column('payment_reference', sa.String(), nullable=True))

    op.execute("UPDATE seat_bookings SET payment_status = 'pending' WHERE payment_status IS NULL")


def downgrade() -> None:
    op.drop_column('seat_bookings', 'payment_reference')
    op.drop_column('seat_bookings', 'payment_method')
    op.drop_column('seat_bookings', 'payment_date')
    op.drop_column('seat_bookings', 'payment_status')
