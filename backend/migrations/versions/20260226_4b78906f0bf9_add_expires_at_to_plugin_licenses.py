"""add expires_at to plugin_licenses

Revision ID: 4b78906f0bf9
Revises: 20260226_0410
Create Date: 2026-02-26 07:28:24.058267+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4b78906f0bf9'
down_revision: Union[str, None] = '20260226_0410'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.add_column(
        'plugin_licenses',
        sa.Column(
            'expires_at', sa.DateTime(), nullable=True,
            comment='付费 License 到期时间（None 表示永久）',
        ),
    )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_column('plugin_licenses', 'expires_at')
