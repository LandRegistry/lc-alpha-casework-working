"""counties

Revision ID: 103621e8dbc
Revises: 1329dff2dd7
Create Date: 2015-11-19 09:31:13.542205

"""

# revision identifiers, used by Alembic.
revision = '103621e8dbc'
down_revision = '1329dff2dd7'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('counties',
                    sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('name', sa.String(), nullable=False),
                    sa.Column('welsh_name', sa.String(), nullable=True)
                    )


def downgrade():
    op.drop_table('counties')
