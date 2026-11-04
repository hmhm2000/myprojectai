"""import subfolders the user unticked (not read by the sync)

Revision ID: a7d3f1c9e2b6
Revises: f1a9c3e5b7d2
Create Date: 2026-11-04 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7d3f1c9e2b6'
down_revision: Union[str, Sequence[str], None] = 'f1a9c3e5b7d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('import_skipped_folders', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.drop_column('import_skipped_folders')
