"""Drop NOT NULL constraint on Review.book_author

Revision ID: 8f1b897458b7
Revises: 220309e50ea0
Create Date: 2021-08-15 19:59:31.110324

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8f1b897458b7'
down_revision = '220309e50ea0'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('reviews', 'book_author',
               existing_type=sa.VARCHAR(),
               nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('reviews', 'book_author',
               existing_type=sa.VARCHAR(),
               nullable=False)
    # ### end Alembic commands ###