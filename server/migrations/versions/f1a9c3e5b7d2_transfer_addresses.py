"""labels of withdrawal addresses (test view of transfers)

Revision ID: f1a9c3e5b7d2
Revises: e8c2f4a6d1b3
Create Date: 2026-10-27 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a9c3e5b7d2'
down_revision: Union[str, Sequence[str], None] = 'e8c2f4a6d1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index('ix_transfer_addresses_user_id', table_name='transfer_addresses')
    op.drop_index('ix_transfer_addresses_id', table_name='transfer_addresses')
    op.drop_table('transfer_addresses')
