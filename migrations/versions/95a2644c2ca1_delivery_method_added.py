"""delivery method added

Revision ID: 95a2644c2ca1
Revises: 8272ebe00f89
Create Date: 2016-01-26 08:32:25.822525

"""

# revision identifiers, used by Alembic.
revision = '95a2644c2ca1'
down_revision = '8272ebe00f89'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    with op.batch_alter_table("pending_application") as batch_op:
        batch_op.add_column(sa.Column('delivery_method', sa.Unicode(), sa.Enum('Portal', 'Fax',
                                                                               'Postal', name='delivery_method')))


def downgrade():
    with op.batch_alter_table("pending_application") as batch_op:
        batch_op.drop_column('delivery_method')
