"""add plugin marketplace fields

Revision ID: 8c70188e6307
Revises: 20260213_plugins
Create Date: 2026-02-13 10:48:22.471162+00:00

NOTE: Original autogenerate output contained ~800 lines of unrelated alter_column
noise on dozens of tables. Cleaned up to keep only the actual plugin marketplace
column additions and plugin/tenant_plugins comment improvements.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8c70188e6307'
down_revision: Union[str, None] = '20260213_plugins'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- New marketplace columns ---
    op.add_column('plugins', sa.Column('downloads_count', sa.Integer(), nullable=False, comment='下载/安装次数（插件市场统计）'))
    op.add_column('plugins', sa.Column('rating', sa.Float(), nullable=True, comment='评分（1.0-5.0，插件市场）'))
    op.add_column('plugins', sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='分类标签（如 ["ai", "adapter", "openai"]）'))
    op.add_column('plugins', sa.Column('category', sa.String(), nullable=True, comment='插件分类（如 ai-model, productivity, analytics）'))
    op.add_column('plugins', sa.Column('screenshots', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='截图 URL 列表（插件市场展示）'))
    op.add_column('plugins', sa.Column('source_url', sa.String(), nullable=True, comment='插件源码仓库 URL（如 GitHub 地址）'))
    op.add_column('plugins', sa.Column('license', sa.String(), nullable=True, comment='开源许可证（如 MIT, Apache-2.0）'))


def downgrade() -> None:
    op.drop_column('plugins', 'license')
    op.drop_column('plugins', 'source_url')
    op.drop_column('plugins', 'screenshots')
    op.drop_column('plugins', 'category')
    op.drop_column('plugins', 'tags')
    op.drop_column('plugins', 'rating')
    op.drop_column('plugins', 'downloads_count')
