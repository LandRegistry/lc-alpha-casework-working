"""add timestamps

Revision ID: 81c74b3d273d
Revises: 3d84c9ac4e2b
Create Date: 2016-03-24 08:57:09.782959

"""

# revision identifiers, used by Alembic.
revision = '81c74b3d273d'
down_revision = '3d84c9ac4e2b'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():

    with op.batch_alter_table("results") as batch_op:
        batch_op.add_column(sa.Column('insert_timestamp', sa.TIMESTAMP()))
        batch_op.add_column(sa.Column('status_timestamp', sa.TIMESTAMP()))
    pass


def downgrade():

    with op.batch_alter_table("results") as batch_op:
        batch_op.drop_column("insert_timestamp")
        batch_op.drop_column("status_timestamp")
    pass
