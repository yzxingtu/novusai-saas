"""add_tier_column_to_ai_models

Revision ID: 8ab691fb6d2e
Revises: 0bc08d7f8260
Create Date: 2026-02-28 23:53:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '8ab691fb6d2e'
down_revision: Union[str, None] = '0bc08d7f8260'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add tier column to ai_models."""
    op.add_column(
        'ai_models',
        sa.Column('tier', sa.String(20), nullable=True, comment='模型级别'),
    )
    op.create_index(op.f('ix_ai_models_tier'), 'ai_models', ['tier'], unique=False)


def downgrade() -> None:
    """Remove tier column from ai_models."""
    op.drop_index(op.f('ix_ai_models_tier'), table_name='ai_models')
    op.drop_column('ai_models', 'tier')
