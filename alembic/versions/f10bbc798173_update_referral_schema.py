"""update_referral_schema

Revision ID: f10bbc798173
Revises: 0585e96f8e45
Create Date: 2025-08-03 12:15:19.740412

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f10bbc798173'
down_revision = '0585e96f8e45'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add user_type column to referral_codes table
    op.add_column('referral_codes', sa.Column('user_type', sa.String(), nullable=True))
    
    # Add new columns to referrals table
    op.add_column('referrals', sa.Column('referrer_type', sa.String(), nullable=True))
    op.add_column('referrals', sa.Column('referred_type', sa.String(), nullable=True))
    op.add_column('referrals', sa.Column('referred_email', sa.String(), nullable=True))
    op.add_column('referrals', sa.Column('points_awarded', sa.String(), nullable=True))
    op.add_column('referrals', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('referrals', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))
    
    # Make referred_id nullable
    op.alter_column('referrals', 'referred_id', nullable=True)


def downgrade() -> None:
    # Remove columns from referrals table
    op.drop_column('referrals', 'completed_at')
    op.drop_column('referrals', 'notes')
    op.drop_column('referrals', 'points_awarded')
    op.drop_column('referrals', 'referred_email')
    op.drop_column('referrals', 'referred_type')
    op.drop_column('referrals', 'referrer_type')
    
    # Remove user_type column from referral_codes table
    op.drop_column('referral_codes', 'user_type')
    
    # Make referred_id not nullable again
    op.alter_column('referrals', 'referred_id', nullable=False)
