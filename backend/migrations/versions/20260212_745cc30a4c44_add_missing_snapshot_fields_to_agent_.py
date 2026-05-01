"""add missing snapshot fields to agent_versions

Revision ID: 745cc30a4c44
Revises: 20260211_0010
Create Date: 2026-02-12 14:03:50.687167+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '745cc30a4c44'
down_revision: Union[str, None] = '20260211_0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.add_column('agent_versions', sa.Column('rag_config', sa.JSON(), nullable=True))
    op.add_column('agent_versions', sa.Column('context_config', sa.JSON(), nullable=True))
    op.add_column('agent_versions', sa.Column('output_schema', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_column('agent_versions', 'output_schema')
    op.drop_column('agent_versions', 'context_config')
    op.drop_column('agent_versions', 'rag_config')
