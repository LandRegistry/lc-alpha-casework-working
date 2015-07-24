"""New columns for worklist gui

Revision ID: 10175932846
Revises: 1878f15107
Create Date: 2015-07-24 08:07:04.895022

"""

# revision identifiers, used by Alembic.
revision = '10175932846'
down_revision = '1878f15107'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('pending_application', sa.Column('status', sa.Unicode()))
    op.add_column('pending_application', sa.Column('assigned_to', sa.Unicode()))
    op.add_column('pending_application', sa.Column('work_type', sa.Unicode()))
    pass


def downgrade():
    op.drop_column('pending_application', 'status')
    op.drop_column('pending_application', 'assigned_to')
    op.drop_column('pending_application', 'work_type')
    pass
