"""create results table

Revision ID: 8272ebe00f89
Revises: aaf3fdd2209a
Create Date: 2016-01-08 08:21:14.781894

"""

# revision identifiers, used by Alembic.
revision = '8272ebe00f89'
down_revision = 'aaf3fdd2209a'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
      op.create_table('results',
                    sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('request_id', sa.Unicode(), nullable=False),
                    sa.Column('res_type', sa.Unicode(), nullable=False),
                    sa.Column('print_status', sa.Unicode(), nullable=False))

def downgrade():
    op.drop_table('results')

