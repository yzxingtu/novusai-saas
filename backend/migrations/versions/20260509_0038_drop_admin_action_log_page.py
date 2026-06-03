"""中文: 移除平台端 AI 操作审计页面权限残留。

EN: Remove residual admin AI action-audit page permissions.

Revision ID: 20260509_0038_admin_actionlog
Revises: 20260508_0037_search_payload
Create Date: 2026-05-09

"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260509_0038_admin_actionlog"
down_revision: str | Sequence[str] | None = "20260508_0037_search_payload"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ADMIN_ACTION_LOG_CODES = (
    "menu:admin.ai_action_log",
    "ai_action_log:list",
    "ai_action_log:detail",
)

PERMISSION_LINK_TABLES = (
    "admin_role_permissions",
    "admin_org_node_permissions",
    "tenant_admin_role_permissions",
    "tenant_user_role_permissions",
    "tenant_plan_permissions",
    "tenant_org_node_permissions",
)


def _has_table(bind: sa.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _columns(bind: sa.Connection, table_name: str) -> set[str]:
    if not _has_table(bind, table_name):
        return set()
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _table(table_name: str, columns: set[str]) -> sa.TableClause:
    typed_columns: dict[str, Any] = {
        "id": sa.Integer(),
        "parent_id": sa.Integer(),
        "permission_id": sa.Integer(),
    }
    return sa.table(
        table_name,
        *(sa.column(name, typed_columns.get(name)) for name in columns),
    )


def _permission_ids(bind: sa.Connection, permissions: sa.TableClause) -> list[int]:
    rows = bind.execute(
        sa.select(permissions.c.id).where(
            permissions.c.scope == "admin",
            sa.or_(
                permissions.c.code.in_(ADMIN_ACTION_LOG_CODES),
                permissions.c.resource == "ai_action_log",
            ),
        )
    ).all()
    return [int(row[0]) for row in rows]


def _admin_call_log_menu_id(
    bind: sa.Connection,
    permissions: sa.TableClause,
) -> int | None:
    row = bind.execute(
        sa.select(permissions.c.id)
        .where(
            permissions.c.scope == "admin",
            permissions.c.code == "menu:admin.ai_call_log",
        )
        .limit(1)
    ).first()
    return int(row[0]) if row else None


def _reparent_permission_children(
    bind: sa.Connection,
    permissions: sa.TableClause,
    retired_ids: list[int],
) -> None:
    if not retired_ids:
        return
    parent_id = _admin_call_log_menu_id(bind, permissions)
    bind.execute(
        sa.update(permissions)
        .where(permissions.c.parent_id.in_(retired_ids))
        .values(parent_id=parent_id)
    )


def _delete_permission_links(bind: sa.Connection, retired_ids: list[int]) -> None:
    if not retired_ids:
        return
    for table_name in PERMISSION_LINK_TABLES:
        columns = _columns(bind, table_name)
        if "permission_id" not in columns:
            continue
        link_table = _table(table_name, columns)
        bind.execute(
            sa.delete(link_table).where(link_table.c.permission_id.in_(retired_ids))
        )


def upgrade() -> None:
    bind = op.get_bind()
    permission_columns = _columns(bind, "permissions")
    required_columns = {"id", "code", "resource", "scope", "parent_id"}
    if not required_columns.issubset(permission_columns):
        return

    permissions = _table("permissions", permission_columns)
    retired_ids = _permission_ids(bind, permissions)
    _reparent_permission_children(bind, permissions, retired_ids)
    _delete_permission_links(bind, retired_ids)
    if retired_ids:
        bind.execute(sa.delete(permissions).where(permissions.c.id.in_(retired_ids)))


def downgrade() -> None:
    pass
