"""add request_id to registered documents

Revision ID: c7136734c0e8
Revises: 83c5b9239476
Create Date: 2016-03-09 13:58:49.127084

"""

# revision identifiers, used by Alembic.
revision = 'c7136734c0e8'
down_revision = '83c5b9239476'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    with op.batch_alter_table("registered_documents") as batch_op:
        batch_op.add_column(sa.Column('request_id', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("registered_documents") as batch_op:
        batch_op.drop_column('request_id')
