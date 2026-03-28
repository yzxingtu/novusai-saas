"""cleanup task binding scope semantics

Revision ID: 20260329_0020
Revises: 20260329_0010
Create Date: 2026-03-29
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260329_0020"
down_revision: str | None = "20260329_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        text(
            """
            DELETE FROM tenant_task_bindings AS tb
            USING task_definitions AS td
            WHERE tb.task_definition_id = td.id
              AND td.scope IN ('admin_only', 'global_shared', 'all_tenants')
            """
        )
    )
    op.execute(
        text(
            """
            DELETE FROM tenant_task_bindings AS tb
            USING tenants AS t
            WHERE tb.tenant_id = t.id
              AND t.is_deleted IS true
            """
        )
    )


def downgrade() -> None:
    # Irreversible data cleanup migration.
    return None
