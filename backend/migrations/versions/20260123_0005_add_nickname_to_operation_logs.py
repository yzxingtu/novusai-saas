# -*- coding: utf-8 -*-
"""add nickname to operation_logs

为 operation_logs 表添加 nickname 字段，用于存储操作用户的昵称

Revision ID: 20260123_0005
Revises: c63b0c9f4a25
Create Date: 2026-01-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260123_0005'
down_revision: Union[str, None] = 'c63b0c9f4a25'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加 nickname 字段"""
    op.add_column('operation_logs', sa.Column(
        'nickname', 
        sa.String(64), 
        nullable=True,
        comment='用户昵称'
    ))


def downgrade() -> None:
    """移除 nickname 字段"""
    op.drop_column('operation_logs', 'nickname')
