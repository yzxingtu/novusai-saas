"""中文: 清退历史系统聊天/向量化技能目录。

EN: Retire historical system chat and embedding skill catalog rows.

Revision ID: 20260513_0044_retire_llm_builtin
Revises: 20260510_0043_task_run_truth
Create Date: 2026-05-13

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "20260513_0044_retire_llm_builtin"
down_revision: str | Sequence[str] | None = "20260510_0043_task_run_truth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_PACKAGE_NAMES = (
    "系统聊天技能包",
    "系统向量化技能包",
    "系统核心技能包",
    "系统引擎技能包",
)
LEGACY_SKILL_NAMES = ("llm_chat", "llm_embedding")
LEGACY_AGENT_NAMES = ("system_chat_agent", "system_embedding_agent")


def _has_table(bind: sa.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _columns(bind: sa.Connection, table_name: str) -> set[str]:
    if not _has_table(bind, table_name):
        return set()
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _has_columns(
    bind: sa.Connection,
    table_name: str,
    column_names: tuple[str, ...],
) -> bool:
    existing = _columns(bind, table_name)
    return all(name in existing for name in column_names)


def _retirement_params() -> dict[str, list[str]]:
    return {
        "legacy_package_names": list(LEGACY_PACKAGE_NAMES),
        "legacy_skill_names": list(LEGACY_SKILL_NAMES),
        "legacy_agent_names": list(LEGACY_AGENT_NAMES),
    }


def _retire_agent_skill_grants(bind: sa.Connection) -> None:
    if not _has_columns(
        bind,
        "agent_skill_grants",
        (
            "skill_id",
            "enabled",
            "is_deleted",
            "deleted_at",
            "delete_level",
            "recycle_stage",
            "promoted_to_global_at",
            "updated_at",
        ),
    ):
        return
    if not _has_columns(bind, "skills", ("id", "package_id", "name")):
        return
    if not _has_columns(
        bind,
        "skill_packages",
        ("id", "name", "tenant_id"),
    ):
        return

    bind.execute(
        text("""
            WITH legacy_packages AS (
                SELECT pkg.id
                FROM skill_packages AS pkg
                WHERE pkg.tenant_id IS NULL
                  AND pkg.name = ANY(:legacy_package_names)
            ),
            legacy_skills AS (
                SELECT skill.id
                FROM skills AS skill
                WHERE skill.name = ANY(:legacy_skill_names)
                   OR skill.package_id IN (SELECT id FROM legacy_packages)
            )
            UPDATE agent_skill_grants AS skill_grant
            SET enabled = false,
                is_deleted = true,
                deleted_at = COALESCE(skill_grant.deleted_at, NOW()),
                delete_level = 'admin',
                recycle_stage = 'module',
                promoted_to_global_at = NULL,
                updated_at = NOW()
            WHERE skill_grant.skill_id IN (SELECT id FROM legacy_skills)
            """),
        _retirement_params(),
    )


def _retire_skills(bind: sa.Connection) -> None:
    required_columns = (
        "id",
        "package_id",
        "name",
        "is_active",
        "is_deleted",
        "deleted_at",
        "delete_level",
        "recycle_stage",
        "promoted_to_global_at",
        "updated_at",
    )
    if not _has_columns(bind, "skills", required_columns):
        return
    if not _has_columns(bind, "skill_packages", ("id", "name", "tenant_id")):
        return

    status_assignment = (
        "status = 'disabled'," if "status" in _columns(bind, "skills") else ""
    )
    bind.execute(
        text(
            """
            WITH legacy_packages AS (
                SELECT pkg.id
                FROM skill_packages AS pkg
                WHERE pkg.tenant_id IS NULL
                  AND pkg.name = ANY(:legacy_package_names)
            )
            UPDATE skills AS skill
            SET is_active = false,
                __STATUS_ASSIGNMENT__
                is_deleted = true,
                deleted_at = COALESCE(skill.deleted_at, NOW()),
                delete_level = 'admin',
                recycle_stage = 'module',
                promoted_to_global_at = NULL,
                updated_at = NOW()
            WHERE (
                    skill.name = ANY(:legacy_skill_names)
                    OR skill.package_id IN (SELECT id FROM legacy_packages)
                  )
            """.replace("__STATUS_ASSIGNMENT__", status_assignment)
        ),
        _retirement_params(),
    )


def _retire_skill_packages(bind: sa.Connection) -> None:
    required_columns = (
        "id",
        "name",
        "tenant_id",
        "is_active",
        "is_deleted",
        "deleted_at",
        "delete_level",
        "recycle_stage",
        "promoted_to_global_at",
        "updated_at",
    )
    if not _has_columns(bind, "skill_packages", required_columns):
        return

    recommended_assignment = (
        "is_recommended = false,"
        if "is_recommended" in _columns(bind, "skill_packages")
        else ""
    )
    bind.execute(
        text(
            """
            UPDATE skill_packages AS pkg
            SET is_active = false,
                __RECOMMENDED_ASSIGNMENT__
                is_deleted = true,
                deleted_at = COALESCE(pkg.deleted_at, NOW()),
                delete_level = 'admin',
                recycle_stage = 'module',
                promoted_to_global_at = NULL,
                updated_at = NOW()
            WHERE pkg.tenant_id IS NULL
              AND pkg.name = ANY(:legacy_package_names)
            """.replace("__RECOMMENDED_ASSIGNMENT__", recommended_assignment)
        ),
        _retirement_params(),
    )


def _retire_system_agents(bind: sa.Connection) -> None:
    required_columns = (
        "id",
        "name",
        "owner_tenant_id",
        "is_system",
        "status",
        "is_deleted",
        "deleted_at",
        "delete_level",
        "recycle_stage",
        "promoted_to_global_at",
        "updated_at",
    )
    if not _has_columns(bind, "agents", required_columns):
        return

    bind.execute(
        text("""
            UPDATE agents AS agent
            SET status = 'disabled',
                is_deleted = true,
                deleted_at = COALESCE(agent.deleted_at, NOW()),
                delete_level = 'admin',
                recycle_stage = 'module',
                promoted_to_global_at = NULL,
                updated_at = NOW()
            WHERE agent.owner_tenant_id IS NULL
              AND agent.is_system = true
              AND agent.name = ANY(:legacy_agent_names)
            """),
        _retirement_params(),
    )


def upgrade() -> None:
    bind = op.get_bind()
    _retire_agent_skill_grants(bind)
    _retire_skills(bind)
    _retire_skill_packages(bind)
    _retire_system_agents(bind)


def downgrade() -> None:
    pass
