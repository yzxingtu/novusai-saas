"""[MERGE] merge_heads

Merges three branches: plm, fix_aa, rmcg.
No schema changes.

Revision ID: f97fd4fbf845
Revises: 20260216_plm, 20260216_fix_aa, 20260216_rmcg
Create Date: 2026-02-16 15:44:33.148717+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f97fd4fbf845'
down_revision: Union[str, None] = ('20260216_plm', '20260216_fix_aa', '20260216_rmcg')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    pass


def downgrade() -> None:
    """Downgrade database schema."""
    pass
