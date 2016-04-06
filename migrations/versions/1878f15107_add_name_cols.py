"""Add Name cols

Revision ID: 1878f15107
Revises: 13e5e8632a6
Create Date: 2015-07-03 13:27:28.848850

"""

# revision identifiers, used by Alembic.
revision = '1878f15107'
down_revision = '13e5e8632a6'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('pending_application',
                  sa.Column('forenames', sa.Unicode())
                  )

    op.add_column('pending_application',
                  sa.Column('surname', sa.Unicode())
                  )
    pass


def downgrade():
    op.drop_column('pending_application', 'forenames')
    op.drop_column('pending_application', 'surname')
    pass
