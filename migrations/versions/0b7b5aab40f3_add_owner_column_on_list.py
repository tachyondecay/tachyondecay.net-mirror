"""Add owner column on List

Revision ID: 0b7b5aab40f3
Revises: 7b3bba6081ed
Create Date: 2021-08-23 23:40:03.594287

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0b7b5aab40f3'
down_revision = '7b3bba6081ed'
branch_labels = None
depends_on = None


def upgrade():
    owner_enum = sa.dialects.postgresql.ENUM(
        'tachyondecay.net', 'kara.reviews', name='lists_owner_enum'
    )
    owner_enum.create(op.get_bind())
    op.add_column('lists', sa.Column('owner', owner_enum))


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('lists', 'owner')
    # ### end Alembic commands ###
    op.execute("DROP TYPE lists_owner_enum;")
