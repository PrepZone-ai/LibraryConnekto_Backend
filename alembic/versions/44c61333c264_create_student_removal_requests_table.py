"""Create student removal requests table

Revision ID: 44c61333c264
Revises: 1ee31fc54504
Create Date: 2025-09-22 00:50:23.654172

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '44c61333c264'
down_revision = '1ee31fc54504'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the removal request status enum (check if it exists first)
    removal_request_status = postgresql.ENUM('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED', name='removalrequeststatus')
    removal_request_status.create(op.get_bind(), checkfirst=True)
    
    # Create the student_removal_requests table
    op.create_table('student_removal_requests',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('admin_id', sa.UUID(), nullable=False),
        sa.Column('reason', sa.TEXT(), nullable=False),
        sa.Column('status', removal_request_status, nullable=False),
        sa.Column('subscription_end_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('days_overdue', sa.VARCHAR(length=50), nullable=False),
        sa.Column('admin_notes', sa.TEXT(), nullable=True),
        sa.Column('processed_by', sa.UUID(), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['admin_id'], ['admin_users.id'], ),
        sa.ForeignKeyConstraint(['processed_by'], ['admin_users.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('student_removal_requests')
    # Drop the enum
    removal_request_status = postgresql.ENUM('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED', name='removalrequeststatus')
    removal_request_status.drop(op.get_bind())
