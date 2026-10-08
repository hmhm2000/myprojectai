"""Import portfolios: portfolios.kind / source / cost_method; import_settings removed

Revision ID: e5a1c7d3b9f2
Revises: d9f2b6c1e4a8
Create Date: 2026-10-08 18:00:00

Every exchange gets its own import portfolio (kind = "import", source = exchange). Existing
portfolios are manual, except those holding imported entries (they become that exchange's
import portfolio). The cost method moves from import_settings to the portfolio.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5a1c7d3b9f2'
down_revision: Union[str, Sequence[str], None] = 'd9f2b6c1e4a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('portfolios') as batch_op:
        batch_op.add_column(sa.Column('kind', sa.String(), nullable=False, server_default='manual'))
        batch_op.add_column(sa.Column('source', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('cost_method', sa.String(), nullable=False, server_default='average'))

    # portfolios with imported entries -> that exchange's import portfolio
    op.execute("""
        UPDATE portfolios SET kind = 'import', source = (
            SELECT MIN(src) FROM (
                SELECT positions.source AS src FROM positions
                 WHERE positions.portfolio_id = portfolios.id AND positions.source != 'manual'
                UNION SELECT account_movements.source FROM account_movements
                 WHERE account_movements.portfolio_id = portfolios.id AND account_movements.source != 'manual'))
        WHERE EXISTS (SELECT 1 FROM positions WHERE positions.portfolio_id = portfolios.id
                      AND positions.source != 'manual')
           OR EXISTS (SELECT 1 FROM account_movements WHERE account_movements.portfolio_id = portfolios.id
                      AND account_movements.source != 'manual')
    """)
    op.execute("""
        UPDATE portfolios SET cost_method = COALESCE(
            (SELECT cost_method FROM import_settings WHERE import_settings.portfolio_id = portfolios.id), 'average')
    """)
    op.drop_table('import_settings')


def downgrade() -> None:
    op.create_table(
        'import_settings',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('portfolio_id', sa.Integer(), sa.ForeignKey('portfolios.id', ondelete='SET NULL'), nullable=True),
        sa.Column('cost_method', sa.String(), nullable=False),
    )
    with op.batch_alter_table('portfolios') as batch_op:
        batch_op.drop_column('cost_method')
        batch_op.drop_column('source')
        batch_op.drop_column('kind')
