"""registered_documents

Revision ID: b912b161b752
Revises: 95a2644c2ca1
Create Date: 2016-02-11 13:02:50.304002

"""

# revision identifiers, used by Alembic.
revision = 'b912b161b752'
down_revision = '95a2644c2ca1'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('registered_documents',
                    sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('number', sa.Integer(), nullable=False),
                    sa.Column('date', sa.Date(), nullable=True),
                    sa.Column('doc_id', sa.Integer())
                    )


def downgrade():
    op.drop_table('registered_documents')
