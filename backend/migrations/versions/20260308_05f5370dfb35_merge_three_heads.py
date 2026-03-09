"""merge_three_heads

Revision ID: 05f5370dfb35
Revises: 20260307_approval, 20260307_backfill_roles, 20260308_init_audience
Create Date: 2026-03-08 19:05:00.134723+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '05f5370dfb35'
down_revision: Union[str, None] = ('20260307_approval', '20260307_backfill_roles', '20260308_init_audience')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    pass


def downgrade() -> None:
    """Downgrade database schema."""
    pass
