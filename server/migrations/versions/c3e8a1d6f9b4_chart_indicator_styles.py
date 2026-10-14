"""Chart indicators: styles of the drawn outputs and own pane height

Revision ID: c3e8a1d6f9b4
Revises: a8c4e1f5d2b7
Create Date: 2026-10-14 22:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3e8a1d6f9b4'
down_revision: Union[str, Sequence[str], None] = 'a8c4e1f5d2b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('chart_indicators') as batch_op:
        batch_op.add_column(sa.Column('styles', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('pane_height', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('chart_indicators') as batch_op:
        batch_op.drop_column('pane_height')
        batch_op.drop_column('styles')
