"""store pending outcomes info

Revision ID: 264195843c
Revises: 103621e8dbc
Create Date: 2015-12-10 13:11:37.921452

"""

# revision identifiers, used by Alembic.
revision = '264195843c'
down_revision = '103621e8dbc'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('results',
                    sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('type', sa.String(), nullable=False),
                    sa.Column('state', sa.Unicode(), nullable=False),
                    sa.Column('number', sa.Integer(), nullable=False),
                    sa.Column('date', sa.DateTime()))


def downgrade():
    op.drop_table('results')
    
    
# insert into results (type, state, number) values ('search', 'new', 7);
# insert into results (type, state, number) values ('search', 'new', 3);
# insert into results (type, state, number, date) values ('search', 'new', 1015, '2014-08-16');