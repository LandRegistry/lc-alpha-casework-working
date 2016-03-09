"""remove null constraint on registered documents

Revision ID: 83c5b9239476
Revises: b912b161b752
Create Date: 2016-03-09 13:39:16.667261

"""

# revision identifiers, used by Alembic.
revision = '83c5b9239476'
down_revision = 'b912b161b752'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute('ALTER TABLE registered_documents ALTER COLUMN number DROP NOT NUll')


def downgrade():
    op.execute('ALTER TABLE registered_documents ALTER COLUMN number SET NOT NUll')
