"""Remove unused table

Revision ID: 153557e4b0db
Revises: 81c74b3d273d
Create Date: 2016-03-30 12:21:32.127681

"""

# revision identifiers, used by Alembic.
revision = '153557e4b0db'
down_revision = '81c74b3d273d'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_table('counties')


def downgrade():
    op.create_table('counties',
                    sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('name', sa.String(), nullable=False),
                    sa.Column('welsh_name', sa.String(), nullable=True)
                    )
