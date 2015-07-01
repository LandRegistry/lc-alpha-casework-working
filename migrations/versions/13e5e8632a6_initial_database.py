"""Initial database

Revision ID: 13e5e8632a6
Revises: 
Create Date: 2015-07-01 14:30:39.652398

"""

# revision identifiers, used by Alembic.
revision = '13e5e8632a6'
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade():
    op.create_table('pending_application',
                    sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('application_data', postgresql.JSON(), nullable=False),
                    sa.Column('date_received', sa.DateTime(), nullable=False),
                    sa.Column('application_type', sa.String(), nullable=False))


def downgrade():
    op.drop_table('pending_application')
