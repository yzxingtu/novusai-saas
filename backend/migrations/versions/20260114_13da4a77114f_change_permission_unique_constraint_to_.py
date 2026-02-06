# -*- coding: utf-8 -*-
"""change permission unique constraint to code+scope

Revision ID: 13da4a77114f
Revises: 20260114_0004
Create Date: 2026-01-14 09:42:46.794448+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '13da4a77114f'
down_revision: Union[str, None] = '20260114_0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # 删除旧的 code 唯一约束
    op.drop_constraint('permissions_code_key', 'permissions', type_='unique')
    # 添加新的 (code, scope) 联合唯一约束
    op.create_unique_constraint('uq_permissions_code_scope', 'permissions', ['code', 'scope'])


def downgrade() -> None:
    """Downgrade database schema."""
    # 删除联合唯一约束
    op.drop_constraint('uq_permissions_code_scope', 'permissions', type_='unique')
    # 恢复旧的 code 唯一约束
    op.create_unique_constraint('permissions_code_key', 'permissions', ['code'])
