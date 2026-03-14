"""add scope column to ai_api_keys

Revision ID: 20260314_add_scope
Revises: 20260314_cleanup_ntpl
Create Date: 2026-03-14 09:14:59.503100+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260314_add_scope'
down_revision: Union[str, None] = '20260314_cleanup_ntpl'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'ai_api_keys',
        sa.Column(
            'scope',
            sa.String(length=20),
            nullable=False,
            server_default='all_tenants',
        ),
    )
    op.create_index('ix_ai_api_keys_scope', 'ai_api_keys', ['scope'])


def downgrade() -> None:
    op.drop_index('ix_ai_api_keys_scope', table_name='ai_api_keys')
    op.drop_column('ai_api_keys', 'scope')
