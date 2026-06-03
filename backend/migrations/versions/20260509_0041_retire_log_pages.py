"""中文: 清理退役日志产品页的权限暴露。

EN: Remove RBAC exposure for retired standalone log product pages.

Revision ID: 20260509_0041_log_pages
Revises: 20260509_0040_drop_ledgers
Create Date: 2026-05-09

"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260509_0041_log_pages"
down_revision: str | Sequence[str] | None = "20260509_0040_drop_ledgers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RETIRED_SURFACES = (
    (
        "admin",
        "operation_log",
        (
            "menu:admin.operation_log",
            "operation_log:list",
            "operation_log:detail",
            "operation_log:delete",
        ),
        "menu:admin.logs",
    ),
    (
        "tenant",
        "operation_log",
        (
            "menu:tenant.operation_log",
            "operation_log:list",
            "operation_log:detail",
        ),
        "menu:tenant.logs",
    ),
    (
        "tenant",
        "ai_action_log",
        (
            "menu:tenant.ai_action_log",
            "ai_action_log:list",
            "ai_action_log:stats",
            "ai_action_log:detail",
        ),
        "menu:tenant.ai_analytics",
    ),
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
        "code": sa.String(),
        "resource": sa.String(),
        "scope": sa.String(),
        "parent_id": sa.Integer(),
        "permission_id": sa.Integer(),
    }
    return sa.table(
        table_name,
        *(sa.column(name, typed_columns.get(name)) for name in columns),
    )


def _retired_conditions(permissions: sa.TableClause) -> list[sa.ColumnElement[bool]]:
    conditions: list[sa.ColumnElement[bool]] = []
    for scope, resource, codes, _fallback_parent_code in RETIRED_SURFACES:
        conditions.append(
            sa.and_(
                permissions.c.scope == scope,
                sa.or_(
                    permissions.c.resource == resource,
                    permissions.c.code.in_(codes),
                ),
            )
        )
    return conditions


def _retired_permission_rows(
    bind: sa.Connection,
    permissions: sa.TableClause,
) -> list[dict[str, Any]]:
    rows = bind.execute(
        sa.select(
            permissions.c.id,
            permissions.c.scope,
            permissions.c.resource,
            permissions.c.code,
        ).where(sa.or_(*_retired_conditions(permissions)))
    ).all()
    return [
        {
            "id": int(row[0]),
            "scope": row[1],
            "resource": row[2],
            "code": row[3],
        }
        for row in rows
    ]


def _permission_id_by_code(
    bind: sa.Connection,
    permissions: sa.TableClause,
    *,
    scope: str,
    code: str,
) -> int | None:
    row = bind.execute(
        sa.select(permissions.c.id)
        .where(
            permissions.c.scope == scope,
            permissions.c.code == code,
        )
        .limit(1)
    ).first()
    return int(row[0]) if row else None


def _surface_retired_ids(
    retired_rows: list[dict[str, Any]],
    *,
    scope: str,
    resource: str,
    codes: Sequence[str],
) -> list[int]:
    code_set = set(codes)
    return [
        int(row["id"])
        for row in retired_rows
        if row["scope"] == scope
        and (row["resource"] == resource or row["code"] in code_set)
    ]


def _reparent_permission_children(
    bind: sa.Connection,
    permissions: sa.TableClause,
    retired_rows: list[dict[str, Any]],
) -> None:
    retired_ids = {int(row["id"]) for row in retired_rows}
    if not retired_ids:
        return

    for scope, resource, codes, fallback_parent_code in RETIRED_SURFACES:
        surface_ids = _surface_retired_ids(
            retired_rows,
            scope=scope,
            resource=resource,
            codes=codes,
        )
        if not surface_ids:
            continue
        fallback_parent_id = _permission_id_by_code(
            bind,
            permissions,
            scope=scope,
            code=fallback_parent_code,
        )
        bind.execute(
            sa.update(permissions)
            .where(
                permissions.c.parent_id.in_(surface_ids),
                ~permissions.c.id.in_(list(retired_ids)),
            )
            .values(parent_id=fallback_parent_id)
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
    retired_rows = _retired_permission_rows(bind, permissions)
    retired_ids = [int(row["id"]) for row in retired_rows]
    _reparent_permission_children(bind, permissions, retired_rows)
    _delete_permission_links(bind, retired_ids)
    if retired_ids:
        bind.execute(sa.delete(permissions).where(permissions.c.id.in_(retired_ids)))


def downgrade() -> None:
    # 中文: 退役页面权限不自动恢复；如需恢复请重新同步当前代码声明的权限。
    # EN: Retired page permissions are not recreated automatically; resync current code declarations if restoration is needed.
    pass
