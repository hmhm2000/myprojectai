"""Positions, sales and new favorite lists (amounts stored as decimal text)

The old portfolio/portfolio_lists/favorites/favorite_lists tables held test data only,
so they are dropped without migrating data. The users table is unchanged.

Revision ID: b7e3c9a1d2f4
Revises: f4ab0f28dae1
Create Date: 2026-10-06 22:40:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e3c9a1d2f4'
down_revision: Union[str, Sequence[str], None] = 'f4ab0f28dae1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('favorites')
    op.drop_table('portfolio')
    op.drop_table('favorite_lists')
    op.drop_table('portfolio_lists')

    op.create_table(
        'portfolios',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_portfolios_id', 'portfolios', ['id'])
    op.create_index('ix_portfolios_user_id', 'portfolios', ['user_id'])

    op.create_table(
        'positions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('portfolio_id', sa.Integer(), sa.ForeignKey('portfolios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('buy_price', sa.String(), nullable=False),
        sa.Column('quantity', sa.String(), nullable=False),
        sa.Column('fee_coin', sa.String(), nullable=False),
        sa.Column('bought_at', sa.DateTime(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_positions_id', 'positions', ['id'])
    op.create_index('ix_positions_portfolio_id', 'positions', ['portfolio_id'])
    op.create_index('ix_positions_symbol', 'positions', ['symbol'])

    op.create_table(
        'sales',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('position_id', sa.Integer(), sa.ForeignKey('positions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('price', sa.String(), nullable=False),
        sa.Column('quantity', sa.String(), nullable=False),
        sa.Column('fee_quote', sa.String(), nullable=False),
        sa.Column('sold_at', sa.DateTime(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_sales_id', 'sales', ['id'])
    op.create_index('ix_sales_position_id', 'sales', ['position_id'])

    op.create_table(
        'favorite_lists',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_favorite_lists_id', 'favorite_lists', ['id'])
    op.create_index('ix_favorite_lists_user_id', 'favorite_lists', ['user_id'])

    op.create_table(
        'favorite_coins',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('list_id', sa.Integer(), sa.ForeignKey('favorite_lists.id', ondelete='CASCADE'), nullable=False),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('added_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('list_id', 'symbol', name='uq_favorite_coin_list_symbol'),
    )
    op.create_index('ix_favorite_coins_id', 'favorite_coins', ['id'])
    op.create_index('ix_favorite_coins_list_id', 'favorite_coins', ['list_id'])


def downgrade() -> None:
    # Recreates empty tables in the old format (data in the new format is lost).
    op.drop_table('favorite_coins')
    op.drop_table('favorite_lists')
    op.drop_table('sales')
    op.drop_table('positions')
    op.drop_table('portfolios')

    op.create_table(
        'portfolio_lists',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
    )
    op.create_table(
        'favorite_lists',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
    )
    op.create_table(
        'portfolio',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('coin_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('buy_price', sa.Float(), nullable=False),
        sa.Column('added_date', sa.String(), nullable=False),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('portfolio_list_id', sa.Integer(), sa.ForeignKey('portfolio_lists.id'), nullable=False),
    )
    op.create_table(
        'favorites',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('coin_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('added_date', sa.String(), nullable=False),
        sa.Column('favorite_list_id', sa.Integer(), sa.ForeignKey('favorite_lists.id'), nullable=False),
    )
