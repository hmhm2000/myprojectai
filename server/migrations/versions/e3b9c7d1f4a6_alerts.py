"""Alerts and alert events

Revision ID: e3b9c7d1f4a6
Revises: d1a7f3b5c802
Create Date: 2026-10-07 22:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e3b9c7d1f4a6'
down_revision: Union[str, Sequence[str], None] = 'd1a7f3b5c802'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'alerts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('interval', sa.String(), nullable=False),
        sa.Column('condition', sa.Text(), nullable=False),
        sa.Column('mode', sa.String(), nullable=False),
        sa.Column('on_closed_candle', sa.Boolean(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('last_state', sa.Boolean(), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.Column('last_triggered_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_alerts_id', 'alerts', ['id'])
    op.create_index('ix_alerts_user_id', 'alerts', ['user_id'])
    op.create_table(
        'alert_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('alert_id', sa.Integer(), sa.ForeignKey('alerts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('triggered_at', sa.DateTime(), nullable=False),
        sa.Column('candle_time', sa.Integer(), nullable=False),
        sa.Column('details', sa.Text(), nullable=False),
        sa.Column('seen', sa.Boolean(), nullable=False),
    )
    op.create_index('ix_alert_events_id', 'alert_events', ['id'])
    op.create_index('ix_alert_events_alert_id', 'alert_events', ['alert_id'])


def downgrade() -> None:
    op.drop_table('alert_events')
    op.drop_table('alerts')
