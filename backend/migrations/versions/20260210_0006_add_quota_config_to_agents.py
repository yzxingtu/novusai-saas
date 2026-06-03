# -*- coding: utf-8 -*-
"""add quota_config to agents

Revision ID: 20260210_0006
Revises: 13da4a77114f
Create Date: 2026-02-10 10:50:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260210_0006'
down_revision: Union[str, None] = '20260210_0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add quota_config JSON column to agents table."""
    op.add_column(
        'agents',
        sa.Column('quota_config', sa.JSON(), nullable=True, comment='智能体配额配置'),
    )


def downgrade() -> None:
    """Remove quota_config column from agents table."""
    op.drop_column('agents', 'quota_config')
