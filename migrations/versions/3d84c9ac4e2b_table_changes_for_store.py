"""Table changes for store

Revision ID: 3d84c9ac4e2b
Revises: c7136734c0e8
Create Date: 2016-03-11 16:09:26.922061

"""

# revision identifiers, used by Alembic.
revision = '3d84c9ac4e2b'
down_revision = 'c7136734c0e8'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    with op.batch_alter_table("pending_application") as batch_op:
        batch_op.add_column(sa.Column('stored', sa.Boolean()))
        batch_op.add_column(sa.Column('stored_by', sa.Unicode()))
        batch_op.add_column(sa.Column('store_reason', sa.Unicode()))
        batch_op.add_column(sa.Column('store_time', sa.DateTime()))

        batch_op.drop_column('forenames')
        batch_op.drop_column('surname')
        batch_op.drop_column('assigned_to')


def downgrade():
    with op.batch_alter_table("pending_application") as batch_op:
        batch_op.add_column(sa.Column('forenames', sa.Unicode()))
        batch_op.add_column(sa.Column('surname', sa.Unicode()))
        batch_op.add_column(sa.Column('assigned_to', sa.Unicode()))
        batch_op.drop_column('stored')
        batch_op.drop_column('stored_by')
        batch_op.drop_column('store_reason')
        batch_op.drop_column('store_time')
