"""add_vision_model_id_and_extract_images_to_knowledge_bases

Revision ID: 0bc08d7f8260
Revises: 4b78906f0bf9
Create Date: 2026-02-28 23:27:38.057037+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0bc08d7f8260'
down_revision: Union[str, None] = '4b78906f0bf9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add vision_model_id and extract_images to knowledge_bases."""
    op.add_column(
        'knowledge_bases',
        sa.Column('vision_model_id', sa.Integer(), nullable=True,
                  comment='Vision 模型'),
    )
    op.add_column(
        'knowledge_bases',
        sa.Column('extract_images', sa.Boolean(), nullable=False,
                  server_default=sa.text('false'), comment='提取图片内容'),
    )
    op.create_index(
        op.f('ix_knowledge_bases_vision_model_id'),
        'knowledge_bases', ['vision_model_id'], unique=False,
    )
    op.create_foreign_key(
        'fk_knowledge_bases_vision_model_id_ai_models',
        'knowledge_bases', 'ai_models',
        ['vision_model_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    """Remove vision_model_id and extract_images from knowledge_bases."""
    op.drop_constraint(
        op.f('fk_knowledge_bases_vision_model_id_ai_models'),
        'knowledge_bases', type_='foreignkey',
    )
    op.drop_index(
        op.f('ix_knowledge_bases_vision_model_id'), table_name='knowledge_bases',
    )
    op.drop_column('knowledge_bases', 'extract_images')
    op.drop_column('knowledge_bases', 'vision_model_id')
