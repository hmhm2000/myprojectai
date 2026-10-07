"""Make favorite_list_id and portfolio_list_id non-nullable

Revision ID: f4ab0f28dae1
Revises: 9c82bcdf9eab
Create Date: 2025-07-31 15:35:20.531028

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4ab0f28dae1'
down_revision: Union[str, Sequence[str], None] = '9c82bcdf9eab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('favorites', schema=None) as batch_op:
        batch_op.alter_column('favorite_list_id', nullable=False)
    with op.batch_alter_table('portfolio', schema=None) as batch_op:
        batch_op.alter_column('portfolio_list_id', nullable=False)

def downgrade() -> None:
    with op.batch_alter_table('favorites', schema=None) as batch_op:
        batch_op.alter_column('favorite_list_id', nullable=True)
    with op.batch_alter_table('portfolio', schema=None) as batch_op:
        batch_op.alter_column('portfolio_list_id', nullable=True)
