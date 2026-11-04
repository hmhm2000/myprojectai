"""drop the labels of withdrawal addresses (the test view of transfers is gone)

Revision ID: b8e4c2d7f1a3
Revises: a7d3f1c9e2b6
Create Date: 2026-11-04 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8e4c2d7f1a3'
down_revision: Union[str, Sequence[str], None] = 'a7d3f1c9e2b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('ix_transfer_addresses_user_id', table_name='transfer_addresses')
    op.drop_index('ix_transfer_addresses_id', table_name='transfer_addresses')
    op.drop_table('transfer_addresses')


def downgrade() -> None:
    op.create_table(
        'transfer_addresses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('address', sa.String(), nullable=False),
        sa.Column('owner', sa.String(), nullable=True),
        sa.Column('label', sa.String(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'address', name='uq_transfer_addresses_user_address'),
    )
    op.create_index('ix_transfer_addresses_id', 'transfer_addresses', ['id'])
    op.create_index('ix_transfer_addresses_user_id', 'transfer_addresses', ['user_id'])
