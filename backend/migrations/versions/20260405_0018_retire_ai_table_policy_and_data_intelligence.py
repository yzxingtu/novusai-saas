"""retire ai table policy and data intelligence

Revision ID: 20260405_retire_ai_policy_di
Revises: 20260405_notif_tpl_cleanup
Create Date: 2026-04-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260405_retire_ai_policy_di"
down_revision: str | Sequence[str] | None = "20260405_notif_tpl_cleanup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def _has_table(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _soft_delete_rows_by_ids(
    bind,
    *,
    table_name: str,
    id_column: str,
    ids: Sequence[int],
) -> None:
    if not ids:
        return
    table = sa.table(
        table_name,
        sa.column(id_column),
        sa.column("is_deleted"),
        sa.column("deleted_at"),
        sa.column("delete_level"),
        sa.column("recycle_stage"),
        sa.column("promoted_to_global_at"),
        sa.column("updated_at"),
    )
    stmt = (
        sa.update(table)
        .where(table.c.is_deleted.is_(False))
        .where(getattr(table.c, id_column).in_(sa.bindparam("ids", expanding=True)))
        .values(
            is_deleted=True,
            deleted_at=sa.func.now(),
            delete_level="admin",
            recycle_stage="module",
            promoted_to_global_at=None,
            updated_at=sa.func.now(),
        )
    )
    bind.execute(stmt, {"ids": list(ids)})


def _collect_data_intelligence_ids(bind) -> tuple[list[int], list[int]]:
    if not _has_table(bind, "skills"):
        return [], []

    rows = bind.execute(
        sa.text(
            """
            SELECT id, package_id
            FROM skills
            WHERE type = 'data_intelligence'
            """
        )
    ).mappings()

    skill_ids: list[int] = []
    package_ids: list[int] = []
    for row in rows:
        skill_ids.append(int(row["id"]))
        package_id = row.get("package_id")
        if package_id is not None and int(package_id) not in package_ids:
            package_ids.append(int(package_id))
    return skill_ids, package_ids


def _soft_delete_data_intelligence_skills(bind) -> None:
    if not _has_table(bind, "skills"):
        return

    bind.execute(
        sa.text(
            """
            UPDATE skills
            SET
                is_deleted = true,
                deleted_at = NOW(),
                delete_level = 'admin',
                recycle_stage = 'module',
                promoted_to_global_at = NULL,
                updated_at = NOW()
            WHERE type = 'data_intelligence'
              AND is_deleted = false
            """
        )
    )


def _soft_delete_grants_for_skills(bind, skill_ids: Sequence[int]) -> None:
    if not skill_ids or not _has_table(bind, "agent_skill_grants"):
        return
    _soft_delete_rows_by_ids(
        bind,
        table_name="agent_skill_grants",
        id_column="skill_id",
        ids=skill_ids,
    )


def _soft_delete_empty_system_packages(
    bind,
    package_ids: Sequence[int],
) -> None:
    if not package_ids or not _has_table(bind, "skill_packages"):
        return
    stmt = (
        sa.text(
            """
            UPDATE skill_packages AS sp
            SET
                is_deleted = true,
                deleted_at = NOW(),
                delete_level = 'admin',
                recycle_stage = 'module',
                promoted_to_global_at = NULL,
                updated_at = NOW()
            WHERE sp.id IN :package_ids
              AND sp.is_system = true
              AND sp.is_deleted = false
              AND NOT EXISTS (
                    SELECT 1
                    FROM skills AS s
                    WHERE s.package_id = sp.id
                      AND s.is_deleted = false
                )
              AND EXISTS (
                    SELECT 1
                    FROM skills AS s
                    WHERE s.package_id = sp.id
                      AND s.type = 'data_intelligence'
                )
            """
        )
        .bindparams(sa.bindparam("package_ids", expanding=True))
    )
    bind.execute(stmt, {"package_ids": list(package_ids)})


def _drop_ai_table_policy_tables(bind) -> None:
    if _has_table(bind, "ai_table_policy_overrides"):
        op.drop_table("ai_table_policy_overrides")
    if _has_table(bind, "ai_table_policies"):
        op.drop_table("ai_table_policies")


def upgrade() -> None:
    bind = op.get_bind()

    skill_ids, package_ids = _collect_data_intelligence_ids(bind)
    _soft_delete_data_intelligence_skills(bind)
    _soft_delete_grants_for_skills(bind, skill_ids)
    _soft_delete_empty_system_packages(bind, package_ids)
    _drop_ai_table_policy_tables(bind)


def downgrade() -> None:
    raise RuntimeError(
        "Retiring AI table policy and data_intelligence is irreversible."
    )
