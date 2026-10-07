"""Sale groups (one sale across several positions) and custom position order

- sales.group_id: sales sharing a group_id are one transaction split across positions.
  Existing sales get their own single-item group.
- positions.sort_order: order set by drag & drop. Existing positions are numbered
  by purchase date.

Revision ID: c4d8e2f6a913
Revises: b7e3c9a1d2f4
Create Date: 2026-10-06 23:30:00

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4d8e2f6a913'
down_revision: Union[str, Sequence[str], None] = 'b7e3c9a1d2f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('positions') as batch_op:
        batch_op.add_column(sa.Column('sort_order', sa.Integer(), nullable=True))
    with op.batch_alter_table('sales') as batch_op:
        batch_op.add_column(sa.Column('group_id', sa.String(length=36), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id FROM positions ORDER BY portfolio_id, bought_at, id")).fetchall()
    for index, (position_id,) in enumerate(rows, start=1):
        conn.execute(sa.text("UPDATE positions SET sort_order = :o WHERE id = :id"), {"o": index, "id": position_id})
    for (sale_id,) in conn.execute(sa.text("SELECT id FROM sales")).fetchall():
        conn.execute(sa.text("UPDATE sales SET group_id = :g WHERE id = :id"), {"g": str(uuid.uuid4()), "id": sale_id})

    with op.batch_alter_table('positions') as batch_op:
        batch_op.alter_column('sort_order', existing_type=sa.Integer(), nullable=False)
    with op.batch_alter_table('sales') as batch_op:
        batch_op.alter_column('group_id', existing_type=sa.String(length=36), nullable=False)
        batch_op.create_index('ix_sales_group_id', ['group_id'])


def downgrade() -> None:
    with op.batch_alter_table('sales') as batch_op:
        batch_op.drop_index('ix_sales_group_id')
        batch_op.drop_column('group_id')
    with op.batch_alter_table('positions') as batch_op:
        batch_op.drop_column('sort_order')
