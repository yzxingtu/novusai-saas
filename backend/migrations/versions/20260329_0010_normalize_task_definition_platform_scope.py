"""normalize task_definition platform scope

Revision ID: 20260329_0010
Revises: 20260327_2030_index_sync
Create Date: 2026-03-29
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260329_0010"
down_revision: str | None = "20260327_2030_index_sync"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_SCOPE = "platform"
_NEW_SCOPE = "admin_only"


def upgrade() -> None:
    op.execute(
        text(
            """
            UPDATE task_definitions
            SET scope = :new_scope
            WHERE scope = :old_scope
            """
        ).bindparams(new_scope=_NEW_SCOPE, old_scope=_OLD_SCOPE)
    )


def downgrade() -> None:
    op.execute(
        text(
            """
            UPDATE task_definitions
            SET scope = :old_scope
            WHERE scope = :new_scope
              AND owner_tenant_id IS NULL
              AND code IN (
                  'task.sync_litellm_registry.e36f21cd',
                  'task.check_plugin_trial_expirations.0b1edeb7'
              )
            """
        ).bindparams(new_scope=_NEW_SCOPE, old_scope=_OLD_SCOPE)
    )
