"""test

Revision ID: 28981bd0a8fd
Revises: 6de5182f2be1
Create Date: 2026-03-19 20:05:42.770173

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '28981bd0a8fd'
down_revision: Union[str, None] = '6de5182f2be1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    pass


def downgrade() -> None:
    """Downgrade database schema."""
    pass
