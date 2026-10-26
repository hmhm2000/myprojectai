"""Bybit import portfolio renamed to "Bybit.eu" (next to the new Bybit.com account)

Revision ID: d4e1a7c3b9f2
Revises: c3e8a1d6f9b4
Create Date: 2026-10-26 18:00:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd4e1a7c3b9f2'
down_revision: Union[str, Sequence[str], None] = 'c3e8a1d6f9b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # only the name given by the import - a name changed by hand stays
    op.execute("UPDATE portfolios SET name = 'Bybit.eu' WHERE kind = 'import' AND source = 'bybit' AND name = 'Bybit'")


def downgrade() -> None:
    op.execute("UPDATE portfolios SET name = 'Bybit' WHERE kind = 'import' AND source = 'bybit' AND name = 'Bybit.eu'")
