"""show_on_chart for positions and sales (presentation only)

Revision ID: f2c6a8e4b1d7
Revises: e3b9c7d1f4a6
Create Date: 2026-10-08 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f2c6a8e4b1d7'
down_revision: Union[str, Sequence[str], None] = 'e3b9c7d1f4a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ('positions', 'sales'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column('show_on_chart', sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    for table in ('sales', 'positions'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column('show_on_chart')
