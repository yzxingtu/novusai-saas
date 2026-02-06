# -*- coding: utf-8 -*-
"""add base_url to attachments table

Revision ID: 20260126_0008
Revises: 20260124_0007
Create Date: 2026-01-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260126_0008"
down_revision: Union[str, None] = "20260124_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 添加 base_url 列
    op.add_column(
        "attachments",
        sa.Column("base_url", sa.String(length=500), nullable=True, comment="文件访问基础URL"),
    )
    
    # 为现有记录设置默认值（根据 driver 推断）
    # 注意：这里使用占位符，实际运行时可能需要根据实际情况调整
    op.execute("""
        UPDATE attachments 
        SET base_url = 'http://localhost:8000/files' 
        WHERE driver = 'local' AND base_url IS NULL
    """)
    
    # 将列改为 NOT NULL（因为旧数据已有值）
    op.alter_column("attachments", "base_url", nullable=False)


def downgrade() -> None:
    op.drop_column("attachments", "base_url")
