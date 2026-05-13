"""add library facility fields

Revision ID: z1y2x3w4v5u6
Revises: q1r2s3t4u5v6
Create Date: 2026-05-12 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

# revision identifiers, used by Alembic.
revision = 'z1y2x3w4v5u6'
down_revision = 'q1r2s3t4u5v6'
branch_labels = None
depends_on = None


def upgrade():
    # Add facility_images column (array of image URLs/paths)
    op.add_column('admin_details', 
        sa.Column('facility_images', ARRAY(sa.String), nullable=True)
    )
    
    # Add facility_description column (100-150 words text)
    op.add_column('admin_details',
        sa.Column('facility_description', sa.Text, nullable=True)
    )


def downgrade():
    op.drop_column('admin_details', 'facility_description')
    op.drop_column('admin_details', 'facility_images')
