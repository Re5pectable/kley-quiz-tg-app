"""init

Revision ID: 8f92e5266676
Revises: b69724b38838
Create Date: 2025-02-11 17:25:23.461247

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f92e5266676'
down_revision: Union[str, None] = 'b69724b38838'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('invitations',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('short_name', sa.String(), nullable=True),
    sa.Column('game_id', sa.UUID(), nullable=True),
    sa.Column('click_counter', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['game_id'], ['games.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_invitations_game_id'), 'invitations', ['game_id'], unique=False)
    op.create_index(op.f('ix_invitations_short_name'), 'invitations', ['short_name'], unique=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_invitations_short_name'), table_name='invitations')
    op.drop_index(op.f('ix_invitations_game_id'), table_name='invitations')
    op.drop_table('invitations')
    # ### end Alembic commands ###
