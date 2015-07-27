"""Table for storing errors

Revision ID: 1329dff2dd7
Revises: 10175932846
Create Date: 2015-07-24 12:41:49.857663

"""

# revision identifiers, used by Alembic.
revision = '1329dff2dd7'
down_revision = '10175932846'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade():
    op.create_table('errors',
                    sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('date_logged', sa.DateTime(), nullable=False),
                    sa.Column('source', sa.Unicode(), nullable=False),
                    sa.Column('data', postgresql.JSON(), nullable=False))


def downgrade():
    op.drop_table('errors^')
