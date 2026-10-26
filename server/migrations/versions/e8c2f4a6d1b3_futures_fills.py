"""futures details of account movements (fills of perpetual / futures positions)

Revision ID: e8c2f4a6d1b3
Revises: d4e1a7c3b9f2
Create Date: 2026-10-26 20:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e8c2f4a6d1b3'
down_revision: Union[str, Sequence[str], None] = 'd4e1a7c3b9f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('account_movements') as batch_op:
        batch_op.add_column(sa.Column('futures', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('account_movements') as batch_op:
        batch_op.drop_column('futures')
