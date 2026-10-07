"""Per-user chart intervals (custom ones and pinned buttons)

Revision ID: b7e3f1a9c2d4
Revises: a5d2e9c4f7b3
Create Date: 2026-10-08 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e3f1a9c2d4'
down_revision: Union[str, Sequence[str], None] = 'a5d2e9c4f7b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chart_intervals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('custom', sa.Boolean(), nullable=False),
        sa.Column('pinned', sa.Boolean(), nullable=False),
        sa.UniqueConstraint('user_id', 'name', name='uq_chart_intervals_user_name'),
    )
    op.create_index('ix_chart_intervals_id', 'chart_intervals', ['id'])
    op.create_index('ix_chart_intervals_user_id', 'chart_intervals', ['user_id'])


def downgrade() -> None:
    op.drop_table('chart_intervals')
