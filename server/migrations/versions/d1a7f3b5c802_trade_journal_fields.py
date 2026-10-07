"""Trade journal: entry reason, tags, plan, target/stop for positions; exit reason for sales

- positions.note -> positions.entry_reason (existing notes are kept)
- positions: new tags, plan, target_price, stop_loss
- sales.note -> sales.exit_reason

Revision ID: d1a7f3b5c802
Revises: c4d8e2f6a913
Create Date: 2026-10-07 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1a7f3b5c802'
down_revision: Union[str, Sequence[str], None] = 'c4d8e2f6a913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('positions') as batch_op:
        batch_op.alter_column('note', new_column_name='entry_reason', existing_type=sa.Text())
        batch_op.add_column(sa.Column('tags', sa.String(), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('plan', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('target_price', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('stop_loss', sa.String(), nullable=True))
    with op.batch_alter_table('sales') as batch_op:
        batch_op.alter_column('note', new_column_name='exit_reason', existing_type=sa.Text())


def downgrade() -> None:
    with op.batch_alter_table('sales') as batch_op:
        batch_op.alter_column('exit_reason', new_column_name='note', existing_type=sa.Text())
    with op.batch_alter_table('positions') as batch_op:
        batch_op.drop_column('stop_loss')
        batch_op.drop_column('target_price')
        batch_op.drop_column('plan')
        batch_op.drop_column('tags')
        batch_op.alter_column('entry_reason', new_column_name='note', existing_type=sa.Text())
