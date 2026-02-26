"""[NO-OP downgrade] remove openai adapter plugin from plugins table (now hardcoded in core)

Revision ID: 20260222_rm_oai
Revises: 20260222_seed_notif
Create Date: 2026-02-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '20260222_rm_oai'
down_revision: Union[str, None] = '20260222_seed_notif'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Delete tenant_plugins associations first
    op.execute(
        sa.text("""
            DELETE FROM tenant_plugins
            WHERE plugin_id IN (
                SELECT id FROM plugins WHERE name = 'novusai-openai-adapter'
            )
        """)
    )
    # Delete the plugin record
    op.execute(
        sa.text("""
            DELETE FROM plugins WHERE name = 'novusai-openai-adapter'
        """)
    )


def downgrade() -> None:
    # Re-insert the plugin record (will be re-registered by plugin system on next startup)
    pass
