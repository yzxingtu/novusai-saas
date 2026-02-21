"""drop_agent_tool_bindings_column

Revision ID: e97db2eecd63
Revises: a5e1ff4cfca1
Create Date: 2026-02-21 03:17:16.660489+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e97db2eecd63'
down_revision: Union[str, None] = 'a5e1ff4cfca1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.drop_column('agents', 'tool_bindings')


def downgrade() -> None:
    """Downgrade database schema."""
    op.add_column('agents', sa.Column(
        'tool_bindings',
        postgresql.JSON(astext_type=sa.Text()),
        autoincrement=False,
        nullable=True,
        comment='enum.agent_model.tool_bindings',
    ))
