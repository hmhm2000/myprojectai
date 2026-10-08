"""Chart indicators: axis_value (value label on the price axis)

Revision ID: f7b3d9e2a6c4
Revises: e5a1c7d3b9f2
Create Date: 2026-10-08 20:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f7b3d9e2a6c4'
down_revision: Union[str, Sequence[str], None] = 'e5a1c7d3b9f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('chart_indicators') as batch_op:
        batch_op.add_column(sa.Column('axis_value', sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('chart_indicators') as batch_op:
        batch_op.drop_column('axis_value')
