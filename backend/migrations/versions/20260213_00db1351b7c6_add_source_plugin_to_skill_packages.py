"""add source_plugin to skill_packages

Revision ID: 00db1351b7c6
Revises: b1c2d3e4f5a6
Create Date: 2026-02-13 20:56:38.631786+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '00db1351b7c6'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.add_column(
        'skill_packages',
        sa.Column(
            'source_plugin',
            sa.String(length=100),
            nullable=True,
            comment='来源插件',
        ),
    )
    op.create_index(
        op.f('ix_skill_packages_source_plugin'),
        'skill_packages',
        ['source_plugin'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_index(
        op.f('ix_skill_packages_source_plugin'),
        table_name='skill_packages',
    )
    op.drop_column('skill_packages', 'source_plugin')
