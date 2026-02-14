"""add scope field to knowledge_bases and agents, make tenant_id nullable

Revision ID: 20a20a8194e9
Revises: 745cc30a4c44
Create Date: 2026-02-12 15:19:34.873605+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20a20a8194e9'
down_revision: Union[str, None] = '745cc30a4c44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # 1. knowledge_bases: add scope, make tenant_id nullable
    op.add_column('knowledge_bases', sa.Column(
        'scope', sa.String(length=20), nullable=False,
        server_default='tenant', comment='资源作用域: tenant/global/admin_only',
    ))
    op.alter_column('knowledge_bases', 'tenant_id',
               existing_type=sa.INTEGER(), nullable=True)
    op.create_index(op.f('ix_knowledge_bases_scope'), 'knowledge_bases', ['scope'], unique=False)

    # 2. agents: add scope, make tenant_id nullable
    op.add_column('agents', sa.Column(
        'scope', sa.String(length=20), nullable=False,
        server_default='tenant', comment='资源作用域: tenant/global/admin_only',
    ))
    op.alter_column('agents', 'tenant_id',
               existing_type=sa.INTEGER(), nullable=True)
    op.create_index(op.f('ix_agents_scope'), 'agents', ['scope'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade database schema."""
    # 1. agents: drop scope, restore tenant_id NOT NULL
    op.drop_index(op.f('ix_agents_scope'), table_name='agents')
    op.drop_column('agents', 'scope')
    op.alter_column('agents', 'tenant_id',
               existing_type=sa.INTEGER(), nullable=False)

    # 2. knowledge_bases: drop scope, restore tenant_id NOT NULL
    op.drop_index(op.f('ix_knowledge_bases_scope'), table_name='knowledge_bases')
    op.drop_column('knowledge_bases', 'scope')
    op.alter_column('knowledge_bases', 'tenant_id',
               existing_type=sa.INTEGER(), nullable=False)
    # ### end Alembic commands ###
