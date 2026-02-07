"""expand_operation_logs_action_column

Revision ID: 676cbd976326
Revises: 20260208_0012
Create Date: 2026-02-07 19:55:06.005303+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '676cbd976326'
down_revision: Union[str, None] = '20260208_0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.alter_column('operation_logs', 'action',
               existing_type=sa.VARCHAR(length=20),
               type_=sa.String(length=50),
               existing_comment='操作类型',
               existing_nullable=True)
    op.alter_column('operation_logs', 'nickname',
               existing_type=sa.VARCHAR(length=64),
               type_=sa.String(length=100),
               existing_comment='用户昵称',
               existing_nullable=True)


def downgrade() -> None:
    """Downgrade database schema."""
    op.alter_column('operation_logs', 'action',
               existing_type=sa.String(length=50),
               type_=sa.VARCHAR(length=20),
               existing_comment='操作类型',
               existing_nullable=True)
    op.alter_column('operation_logs', 'nickname',
               existing_type=sa.String(length=100),
               type_=sa.VARCHAR(length=64),
               existing_comment='用户昵称',
               existing_nullable=True)
