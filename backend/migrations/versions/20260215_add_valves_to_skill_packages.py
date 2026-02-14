"""add valves_schema and valves_config to skill_packages

Add JSONB columns for storing environment variable configuration schema
(parsed from .env.example) and user-provided configuration values.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-02-15 12:00:00.000000+08:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'skill_packages',
        sa.Column('valves_schema', postgresql.JSONB(), nullable=True,
                  comment='配置项定义（JSON Schema）'),
    )
    op.add_column(
        'skill_packages',
        sa.Column('valves_config', postgresql.JSONB(), nullable=True,
                  comment='配置项值（用户填写）'),
    )


def downgrade() -> None:
    op.drop_column('skill_packages', 'valves_config')
    op.drop_column('skill_packages', 'valves_schema')
