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
    # The student_removal_requests table and the removalrequeststatus enum
    # are already created by the previous revision (1ee31fc54504). This
    # revision is kept as a no-op so the migration chain is preserved.
    pass


def downgrade() -> None:
    pass
