"""Per-user chart indicator settings

Revision ID: a5d2e9c4f7b3
Revises: f2c6a8e4b1d7
Create Date: 2026-10-08 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a5d2e9c4f7b3'
down_revision: Union[str, Sequence[str], None] = 'f2c6a8e4b1d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chart_indicators',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('indicator_id', sa.String(), nullable=False),
        sa.Column('params', sa.Text(), nullable=False),
        sa.Column('interval', sa.String(), nullable=True),
        sa.Column('visible', sa.Boolean(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_chart_indicators_id', 'chart_indicators', ['id'])
    op.create_index('ix_chart_indicators_user_id', 'chart_indicators', ['user_id'])


def downgrade() -> None:
    op.drop_table('chart_indicators')
