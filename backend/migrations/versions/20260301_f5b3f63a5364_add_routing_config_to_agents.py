"""add_routing_config_to_agents

Revision ID: f5b3f63a5364
Revises: 8ab691fb6d2e
Create Date: 2026-03-01 00:08:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f5b3f63a5364'
down_revision: Union[str, None] = '8ab691fb6d2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add routing_config JSON column to agents."""
    op.add_column(
        'agents',
        sa.Column('routing_config', postgresql.JSON(astext_type=sa.Text()),
                  nullable=True, comment='多模型路由配置'),
    )


def downgrade() -> None:
    """Remove routing_config column from agents."""
    op.drop_column('agents', 'routing_config')
