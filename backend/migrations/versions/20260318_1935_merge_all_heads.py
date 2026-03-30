"""merge_all_heads

Revision ID: 6de5182f2be1
Revises: 20260319_codegen_resource_uq, 20260321_page_op_boundary
Create Date: 2026-03-18 19:35:19.767620+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6de5182f2be1'
down_revision: Union[str, None] = (
    '20260319_codegen_resource_uq',
    '20260321_page_op_boundary',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    pass


def downgrade() -> None:
    """Intentional no-op: Merge revision only; no schema changes to reverse."""
    pass
