"""[MERGE] merge_img_limits_and_fix_tz

Merges two branches: img_limits, fix_tz.
No schema changes.

Revision ID: a5e1ff4cfca1
Revises: 20260221_img_limits, 20260221_fix_tz
Create Date: 2026-02-21 03:04:29.906389+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a5e1ff4cfca1'
down_revision: Union[str, None] = ('20260221_img_limits', '20260221_fix_tz')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    pass


def downgrade() -> None:
    """Intentional no-op: Merge revision only; no schema changes to reverse."""
    pass
