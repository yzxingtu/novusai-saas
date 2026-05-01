"""Update "平台数据管理" package and skill descriptions for __ai_policy__ declarative model

平台数据管理技能包/技能描述更新，体现声明式 __ai_policy__ 机制。

Revision ID: 20260320_data_mgmt_desc
Revises: 20260319_retired_runtime
Create Date: 2026-03-20 00:00:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260320_data_mgmt_desc"
down_revision: str | Sequence[str] | None = "20260319_retired_runtime"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PKG_DESC = (
    "平台数据管理能力包。包含数据智能、Text-to-SQL 等数据操作技能，仅限管理端使用。"
    "仅对声明了 __ai_policy__ 的数据表生效。"
)
SKILL_DESC = (
    "平台管理员的数据操作技能。自动使用所有已配置的表策略（仅限声明了 __ai_policy__ 的表），"
    "支持自然语言查询（Text-to-SQL）和 CRUD 操作。"
)


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "UPDATE skill_packages SET description = :desc, updated_at = NOW() "
            "WHERE name = '平台数据管理' AND is_system = true AND is_deleted = false"
        ),
        {"desc": PKG_DESC},
    )
    conn.execute(
        text(
            "UPDATE skills SET description = :desc, updated_at = NOW() "
            "WHERE name = '平台数据管理' AND is_system = true "
            "AND type = 'data_intelligence' AND is_deleted = false"
        ),
        {"desc": SKILL_DESC},
    )


def downgrade() -> None:
    conn = op.get_bind()
    old_pkg = (
        "平台数据管理能力包。包含数据智能、Text-to-SQL 等数据操作技能，仅限管理端使用。"
    )
    old_skill = (
        "数据智能技能：自动使用所有已配置的表策略，"
        "支持自然语言查询（Text-to-SQL）和 CRUD 操作，"
        "仅限管理端使用。"
    )
    conn.execute(
        text(
            "UPDATE skill_packages SET description = :desc, updated_at = NOW() "
            "WHERE name = '平台数据管理' AND is_system = true AND is_deleted = false"
        ),
        {"desc": old_pkg},
    )
    conn.execute(
        text(
            "UPDATE skills SET description = :desc, updated_at = NOW() "
            "WHERE name = '平台数据管理' AND is_system = true "
            "AND type = 'data_intelligence' AND is_deleted = false"
        ),
        {"desc": old_skill},
    )
