"""add AI model rate limit fields

Revision ID: 20260208_003_add_ai_model_limits
Revises: 20260207_002_add_ai_usage_stats
Create Date: 2026-02-08 06:06:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260208_003_add_ai_model_limits'
down_revision = '20260207_002_add_ai_usage_stats'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 添加 rpm_limit 和 tpm_limit 字段到 ai_models 表
    with op.batch_alter_table("ai_models") as batch:
        batch.add_column(
            sa.Column('rpm_limit', sa.Integer(), nullable=True, comment='RPM 限制(每分钟请求数)')
        )
        batch.add_column(
            sa.Column('tpm_limit', sa.Integer(), nullable=True, comment='TPM 限制(每分钟 Token 数)')
        )


def downgrade() -> None:
    # 删除添加的字段
    with op.batch_alter_table("ai_models") as batch:
        batch.drop_column("rpm_limit")
        batch.drop_column("tpm_limit")
