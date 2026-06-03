"""Rename ai_skill_registry permission resource to plugin_skill_registry

Revision ID: 20260330_0110_permrename
"""

from typing import Sequence

from migrations.helpers import safe_rename_permission_resource

revision: str = "20260330_0110_permrename"
down_revision: str | Sequence[str] | None = "20260330_0100_calltrace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    safe_rename_permission_resource("ai_skill_registry", "plugin_skill_registry")


def downgrade() -> None:
    safe_rename_permission_resource("plugin_skill_registry", "ai_skill_registry")
