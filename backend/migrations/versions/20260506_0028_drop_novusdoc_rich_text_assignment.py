"""中文: 移除旧 NovusDoc 富文本插件功能分配行。

EN: Remove the legacy NovusDoc rich-text plugin assignment row.

Revision ID: 20260506_0028_drop_novus_rich
Revises: 20260505_0027_novusdoc_richai
Create Date: 2026-05-06

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "20260506_0028_drop_novus_rich"
down_revision: str | Sequence[str] | None = "20260505_0027_novusdoc_richai"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_FEATURE_CODE = "plugin.novusdoc.rich_text_ai"
RUNTIME_FEATURE_CODE = "system.ai_writing"
LEGACY_FEATURE_NAME = "NovusDoc Rich Text AI"
LEGACY_FEATURE_DESCRIPTION = (
    "Scene-specific AI assignment for the NovusDoc rich-text editor. Supports "
    "continue, rewrite, insert, formatting, translate, proofread, summarize, "
    "expand, custom instruction, and chat actions."
)


def _has_table(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """中文: 旧插件行不是新版富文本 AI 的运行时入口，删除以避免双入口误判。

    EN: Delete the legacy plugin row because the runtime resolver uses only
    system.ai_writing for the current rich-text AI flow.
    """
    bind = op.get_bind()
    if not _has_table(bind, "system_agent_assignments"):
        return
    bind.execute(
        text("""
            DELETE FROM system_agent_assignments
            WHERE feature_code = :legacy_feature_code
              AND tenant_id IS NULL
              AND is_deleted = false
            """),
        {"legacy_feature_code": LEGACY_FEATURE_CODE},
    )


def downgrade() -> None:
    """中文: 降级时恢复旧插件功能行，但不重新引入运行时优先级。

    EN: Restore the legacy plugin feature row on downgrade without changing the
    runtime feature priority.
    """
    bind = op.get_bind()
    if not _has_table(bind, "system_agent_assignments"):
        return
    bind.execute(
        text("""
            WITH runtime_assignment AS (
                SELECT agent_id
                FROM system_agent_assignments
                WHERE feature_code = :runtime_feature_code
                  AND tenant_id IS NULL
                  AND is_deleted = false
                ORDER BY id
                LIMIT 1
            )
            INSERT INTO system_agent_assignments (
                feature_code, feature_name, description, tenant_id, agent_id,
                config, is_active, created_at, updated_at, is_deleted
            )
            SELECT
                :legacy_feature_code,
                :legacy_feature_name,
                :legacy_feature_description,
                NULL,
                runtime_assignment.agent_id,
                NULL,
                true,
                NOW(),
                NOW(),
                false
            FROM (SELECT 1) AS seed
            LEFT JOIN runtime_assignment ON true
            WHERE NOT EXISTS (
                SELECT 1
                FROM system_agent_assignments
                WHERE feature_code = :legacy_feature_code
                  AND tenant_id IS NULL
                  AND is_deleted = false
            )
            """),
        {
            "legacy_feature_code": LEGACY_FEATURE_CODE,
            "legacy_feature_description": LEGACY_FEATURE_DESCRIPTION,
            "legacy_feature_name": LEGACY_FEATURE_NAME,
            "runtime_feature_code": RUNTIME_FEATURE_CODE,
        },
    )
