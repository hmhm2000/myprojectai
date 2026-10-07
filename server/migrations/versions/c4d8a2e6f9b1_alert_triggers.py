"""Alert trigger modes (intrabar / bar_open / bar_close) instead of on_closed_candle

Revision ID: c4d8a2e6f9b1
Revises: b7e3f1a9c2d4
Create Date: 2026-10-08 20:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4d8a2e6f9b1'
down_revision: Union[str, Sequence[str], None] = 'b7e3f1a9c2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('alerts') as batch_op:
        batch_op.add_column(sa.Column('trigger', sa.String(), nullable=False, server_default='bar_close'))
        batch_op.add_column(sa.Column('last_candle_time', sa.Integer(), nullable=True))
    # on_closed_candle = False meant "evaluate the forming candle" -> intrabar
    op.execute("UPDATE alerts SET \"trigger\" = 'intrabar' WHERE on_closed_candle = 0")
    with op.batch_alter_table('alerts') as batch_op:
        batch_op.drop_column('on_closed_candle')


def downgrade() -> None:
    with op.batch_alter_table('alerts') as batch_op:
        batch_op.add_column(sa.Column('on_closed_candle', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.execute("UPDATE alerts SET on_closed_candle = 0 WHERE \"trigger\" = 'intrabar'")
    with op.batch_alter_table('alerts') as batch_op:
        batch_op.drop_column('last_candle_time')
        batch_op.drop_column('trigger')
