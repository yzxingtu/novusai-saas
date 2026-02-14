"""add skill_id to ai_action_logs

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'ai_action_logs',
        sa.Column('skill_id', sa.Integer(), nullable=True, comment='Source Skill ID'),
    )
    op.create_index('idx_ai_action_logs_skill_id', 'ai_action_logs', ['skill_id'])


def downgrade() -> None:
    op.drop_index('idx_ai_action_logs_skill_id', table_name='ai_action_logs')
    op.drop_column('ai_action_logs', 'skill_id')
