"""add request_metadata to ai_call_logs

Revision ID: 147c588d9898
Revises: 20260208_005_add_model_fallback
Create Date: 2026-02-08 21:04:09.130412+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '147c588d9898'
down_revision: Union[str, None] = '20260208_005_add_model_fallback'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.add_column(
        'ai_call_logs',
        sa.Column('request_metadata', sa.JSON(), nullable=True, comment='enum.ai_call_log.request_metadata')
    )
    op.drop_column('ai_call_logs', 'metadata')


def downgrade() -> None:
    """Downgrade database schema."""
    op.add_column(
        'ai_call_logs',
        sa.Column('metadata', sa.JSON(), nullable=True)
    )
    op.drop_column('ai_call_logs', 'request_metadata')
