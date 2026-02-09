"""add model fallback_model_id

Revision ID: 20260208_005_add_model_fallback
Revises: 20260208_004_add_tenant_quotas
Create Date: 2026-02-08
"""

import sqlalchemy as sa
from alembic import op

revision = '20260208_005_add_model_fallback'
down_revision = '20260208_004_add_tenant_quotas'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 新增 fallback_model_id 字段
    op.add_column(
        'ai_models',
        sa.Column(
            'fallback_model_id',
            sa.Integer(),
            sa.ForeignKey('ai_models.id', name='fk_ai_models_fallback_model_id', ondelete='SET NULL'),
            nullable=True,
            comment='备用模型 ID（故障转移链）',
        )
    )
    op.create_index('ix_ai_models_fallback_model_id', 'ai_models', ['fallback_model_id'])


def downgrade() -> None:
    op.drop_index('ix_ai_models_fallback_model_id', table_name='ai_models')
    op.drop_column('ai_models', 'fallback_model_id')
