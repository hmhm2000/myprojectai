"""Chart indicators: slot (chart window of a split layout)

Revision ID: a8c4e1f5d2b7
Revises: f7b3d9e2a6c4
Create Date: 2026-10-14 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a8c4e1f5d2b7'
down_revision: Union[str, Sequence[str], None] = 'f7b3d9e2a6c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('chart_indicators') as batch_op:
        batch_op.add_column(sa.Column('slot', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('chart_indicators') as batch_op:
        batch_op.drop_column('slot')
