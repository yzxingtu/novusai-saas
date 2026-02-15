"""drop batch_project_snapshot column from crud_generation_records

Single-table refactor: remove multi-table batch generation support.
The batch_project_snapshot column is no longer needed.

Revision ID: aa0215030000
Revises: aa0215020000
Create Date: 2026-02-15 19:30:00.000000+08:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aa0215030000"
down_revision: Union[str, None] = "aa0215020000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("crud_generation_records", "batch_project_snapshot")


def downgrade() -> None:
    op.add_column(
        "crud_generation_records",
        sa.Column("batch_project_snapshot", sa.JSON(), nullable=True),
    )
