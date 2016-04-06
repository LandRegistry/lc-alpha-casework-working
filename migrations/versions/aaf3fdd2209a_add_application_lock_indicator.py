"""Add application lock indicator

Revision ID: aaf3fdd2209a
Revises: 132d8e55a6b
Create Date: 2016-01-06 10:43:55.260949

"""

# revision identifiers, used by Alembic.
revision = 'aaf3fdd2209a'
down_revision = '132d8e55a6b'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('pending_application', sa.Column('lock_ind', sa.Unicode(length=1)))
    pass


def downgrade():
    op.drop_column('pending_application', 'lock_ind')
    pass
