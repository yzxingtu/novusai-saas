# -*- coding: utf-8 -*-
"""add context_config and output_schema to agents

Revision ID: 20260210_0009
Revises: 20260210_0008
Create Date: 2026-02-10 15:12:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260210_0009'
down_revision: Union[str, None] = '20260210_0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add context_config and output_schema columns to agents."""
    op.add_column(
        'agents',
        sa.Column('context_config', sa.JSON(), nullable=True),
    )
    op.add_column(
        'agents',
        sa.Column('output_schema', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Remove context_config and output_schema from agents."""
    op.drop_column('agents', 'output_schema')
    op.drop_column('agents', 'context_config')
