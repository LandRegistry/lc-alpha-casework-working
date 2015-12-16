"""create document table

Revision ID: 132d8e55a6b
Revises: 103621e8dbc
Create Date: 2015-12-10 14:56:21.287909

"""

# revision identifiers, used by Alembic.
revision = '132d8e55a6b'
down_revision = '103621e8dbc'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade():
    op.create_table('documents',
                    sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('document_id', sa.Integer()),
                    sa.Column('form_type', sa.Unicode()),
                    sa.Column('content_type', sa.Unicode()),
                    sa.Column('page', sa.Integer()),
                    sa.Column('size', sa.Unicode()),
                    sa.Column('image', sa.LargeBinary()))


def downgrade():
    op.drop_table('documents')
