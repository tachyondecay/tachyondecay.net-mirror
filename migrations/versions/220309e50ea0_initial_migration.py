"""Initial migration.

Revision ID: 220309e50ea0
Revises: 
Create Date: 2021-08-15 19:57:05.416223

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '220309e50ea0'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint(op.f('uq_revisions_id'), 'revisions', ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(op.f('uq_revisions_id'), 'revisions', type_='unique')
    # ### end Alembic commands ###
