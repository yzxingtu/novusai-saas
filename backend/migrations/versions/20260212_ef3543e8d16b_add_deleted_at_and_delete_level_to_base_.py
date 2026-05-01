"""add deleted_at and delete_level to base model

Revision ID: ef3543e8d16b
Revises: 8d11e316fec0
Create Date: 2026-02-12 20:47:47.955375+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ef3543e8d16b'
down_revision: Union[str, None] = '8d11e316fec0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = [
    'admin_roles',
    'admins',
    'agent_access',
    'agent_conversations',
    'agent_versions',
    'agents',
    'ai_action_logs',
    'ai_api_keys',
    'ai_call_logs',
    'ai_models',
    'ai_providers',
    'ai_query_logs',
    'attachments',
    'batch_runs',
    'conversation_messages',
    'document_chunks',
    'knowledge_bases',
    'knowledge_documents',
    'operation_logs',
    'permissions',
    'system_config_groups',
    'system_config_values',
    'system_configs',
    'tenant_admin_roles',
    'tenant_admins',
    'tenant_domains',
    'tenant_model_rate_limits',
    'tenant_plans',
    'tenant_quotas',
    'tenant_users',
    'tenants',
]


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column(
            'deleted_at', sa.DateTime(), nullable=True, comment='删除时间',
        ))
        op.add_column(table, sa.Column(
            'delete_level', sa.String(length=20), nullable=True,
            comment='删除层级: tenant=企业回收站, admin=管理端回收站',
        ))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_column(table, 'delete_level')
        op.drop_column(table, 'deleted_at')
