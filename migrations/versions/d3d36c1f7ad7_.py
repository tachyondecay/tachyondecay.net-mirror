"""empty message

Revision ID: d3d36c1f7ad7
Revises: 0b7b5aab40f3
Create Date: 2021-12-04 14:28:00.417547

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3d36c1f7ad7'
down_revision = '0b7b5aab40f3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('reviews', sa.Column('storygraph_id', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('reviews', 'storygraph_id')
    # ### end Alembic commands ###
