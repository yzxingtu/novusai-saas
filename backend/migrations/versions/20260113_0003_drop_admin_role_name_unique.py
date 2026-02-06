# -*- coding: utf-8 -*-
"""drop admin_roles name unique constraint

Revision ID: 20260113_0003
Revises: 20260112_0002
Create Date: 2026-01-13

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '20260113_0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """移除 admin_roles.name 的唯一约束"""
    op.drop_constraint('admin_roles_name_key', 'admin_roles', type_='unique')


def downgrade() -> None:
    """恢复 admin_roles.name 的唯一约束"""
    op.create_unique_constraint('admin_roles_name_key', 'admin_roles', ['name'])
