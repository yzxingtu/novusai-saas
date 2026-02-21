"""add max_image_count and max_image_size_mb to ai_models

Revision ID: 20260221_img_limits
Revises: 20260221_seed_ssl
Create Date: 2026-02-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '20260221_img_limits'
down_revision: Union[str, None] = '20260221_seed_ssl'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'ai_models',
        sa.Column('max_image_count', sa.Integer(), nullable=True, server_default='5'),
    )
    op.add_column(
        'ai_models',
        sa.Column('max_image_size_mb', sa.Integer(), nullable=True, server_default='10'),
    )


def downgrade() -> None:
    op.drop_column('ai_models', 'max_image_size_mb')
    op.drop_column('ai_models', 'max_image_count')
