"""test2

Revision ID: 50962e419df2
Revises: 28981bd0a8fd
Create Date: 2026-03-19 20:05:48.791733

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '50962e419df2'
down_revision: Union[str, None] = '28981bd0a8fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    pass


def downgrade() -> None:
    """Downgrade database schema."""
    pass
