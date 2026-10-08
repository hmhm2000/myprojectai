"""Exchange CSV import: source/external_id on positions and sales, import files, changes, movements

Revision ID: d9f2b6c1e4a8
Revises: c4d8a2e6f9b1
Create Date: 2026-10-08 12:00:00

Existing positions and sales get source = "manual".
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd9f2b6c1e4a8'
down_revision: Union[str, Sequence[str], None] = 'c4d8a2e6f9b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

IMPORT_COLUMNS = ('source', 'external_id', 'fingerprint', 'raw', 'import_file_id', 'imported_at',
                  'missing_in_export', 'note', 'custom_fields')


def _import_columns(batch_op, table):
    batch_op.add_column(sa.Column('source', sa.String(), nullable=False, server_default='manual'))
    batch_op.add_column(sa.Column('external_id', sa.String(), nullable=True))
    batch_op.add_column(sa.Column('fingerprint', sa.String(), nullable=True))
    batch_op.add_column(sa.Column('raw', sa.Text(), nullable=True))
    batch_op.add_column(sa.Column('import_file_id', sa.Integer(), nullable=True))
    batch_op.add_column(sa.Column('imported_at', sa.DateTime(), nullable=True))
    batch_op.add_column(sa.Column('missing_in_export', sa.Boolean(), nullable=False, server_default=sa.false()))
    batch_op.add_column(sa.Column('note', sa.Text(), nullable=True))
    batch_op.add_column(sa.Column('custom_fields', sa.Text(), nullable=True))
    batch_op.create_foreign_key(f'fk_{table}_import_file', 'import_files', ['import_file_id'], ['id'], ondelete='SET NULL')
    batch_op.create_index(f'ix_{table}_external_id', ['external_id'])
    batch_op.create_index(f'ix_{table}_fingerprint', ['fingerprint'])


def upgrade() -> None:
    op.create_table(
        'import_files',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('imported_at', sa.DateTime(), nullable=False),
        sa.Column('rows_total', sa.Integer(), nullable=False),
        sa.Column('rows_new', sa.Integer(), nullable=False),
        sa.Column('rows_updated', sa.Integer(), nullable=False),
        sa.Column('rows_skipped', sa.Integer(), nullable=False),
        sa.Column('rows_unchanged', sa.Integer(), nullable=False),
        sa.Column('warnings', sa.Text(), nullable=False),
        sa.UniqueConstraint('user_id', 'sha256', name='uq_import_files_user_sha256'),
    )
    op.create_index('ix_import_files_id', 'import_files', ['id'])
    op.create_index('ix_import_files_user_id', 'import_files', ['user_id'])

    op.create_table(
        'import_changes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('external_id', sa.String(), nullable=False),
        sa.Column('field', sa.String(), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('file_id', sa.Integer(), sa.ForeignKey('import_files.id', ondelete='SET NULL'), nullable=True),
        sa.Column('changed_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_import_changes_id', 'import_changes', ['id'])
    op.create_index('ix_import_changes_user_id', 'import_changes', ['user_id'])
    op.create_index('ix_import_changes_external_id', 'import_changes', ['external_id'])

    op.create_table(
        'account_movements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('portfolio_id', sa.Integer(), sa.ForeignKey('portfolios.id', ondelete='SET NULL'), nullable=True),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('quantity', sa.String(), nullable=False),
        sa.Column('price', sa.String(), nullable=True),
        sa.Column('fee', sa.String(), nullable=True),
        sa.Column('value_usd', sa.String(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('external_id', sa.String(), nullable=True),
        sa.Column('fingerprint', sa.String(), nullable=True),
        sa.Column('raw', sa.Text(), nullable=True),
        sa.Column('import_file_id', sa.Integer(), sa.ForeignKey('import_files.id', ondelete='SET NULL'), nullable=True),
        sa.Column('imported_at', sa.DateTime(), nullable=True),
        sa.Column('missing_in_export', sa.Boolean(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('custom_fields', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('user_id', 'source', 'external_id', name='uq_account_movements_external'),
    )
    op.create_index('ix_account_movements_id', 'account_movements', ['id'])
    op.create_index('ix_account_movements_user_id', 'account_movements', ['user_id'])
    op.create_index('ix_account_movements_portfolio_id', 'account_movements', ['portfolio_id'])
    op.create_index('ix_account_movements_fingerprint', 'account_movements', ['fingerprint'])

    op.create_table(
        'import_settings',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('portfolio_id', sa.Integer(), sa.ForeignKey('portfolios.id', ondelete='SET NULL'), nullable=True),
        sa.Column('cost_method', sa.String(), nullable=False),
    )

    for table in ('positions', 'sales'):
        with op.batch_alter_table(table) as batch_op:
            _import_columns(batch_op, table)


def downgrade() -> None:
    for table in ('sales', 'positions'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_index(f'ix_{table}_fingerprint')
            batch_op.drop_index(f'ix_{table}_external_id')
            batch_op.drop_constraint(f'fk_{table}_import_file', type_='foreignkey')
            for column in reversed(IMPORT_COLUMNS):
                batch_op.drop_column(column)
    op.drop_table('import_settings')
    op.drop_table('account_movements')
    op.drop_table('import_changes')
    op.drop_table('import_files')
