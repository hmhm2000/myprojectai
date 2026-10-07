from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '9c82bcdf9eab'
down_revision: Union[str, Sequence[str], None] = 'd61e89a23bdc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)

    op.create_table(
        'favorite_lists',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_favorite_lists_user_id'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_favorite_lists_id'), 'favorite_lists', ['id'], unique=False)

    op.create_table(
        'portfolio_lists',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_portfolio_lists_user_id'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_portfolio_lists_id'), 'portfolio_lists', ['id'], unique=False)

    with op.batch_alter_table('favorites', schema=None) as batch_op:
        batch_op.add_column(sa.Column('favorite_list_id', sa.Integer(), nullable=True))  # Tymczasowo nullable=True
        batch_op.create_foreign_key('fk_favorites_favorite_list_id', 'favorite_lists', ['favorite_list_id'], ['id'])

    with op.batch_alter_table('portfolio', schema=None) as batch_op:
        batch_op.add_column(sa.Column('portfolio_list_id', sa.Integer(), nullable=True))  # Tymczasowo nullable=True
        batch_op.create_foreign_key('fk_portfolio_portfolio_list_id', 'portfolio_lists', ['portfolio_list_id'], ['id'])

def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('portfolio', schema=None) as batch_op:
        batch_op.drop_constraint('fk_portfolio_portfolio_list_id', type_='foreignkey')
        batch_op.drop_column('portfolio_list_id')

    with op.batch_alter_table('favorites', schema=None) as batch_op:
        batch_op.drop_constraint('fk_favorites_favorite_list_id', type_='foreignkey')
        batch_op.drop_column('favorite_list_id')

    op.drop_index(op.f('ix_portfolio_lists_id'), table_name='portfolio_lists')
    op.drop_table('portfolio_lists')

    op.drop_index(op.f('ix_favorite_lists_id'), table_name='favorite_lists')
    op.drop_table('favorite_lists')

    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')