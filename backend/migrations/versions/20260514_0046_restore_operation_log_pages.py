"""中文: 恢复操作日志产品页的权限暴露。

EN: Restore RBAC exposure for operation log product pages.

Revision ID: 20260514_0046_oplog_surface
Revises: 20260513_0045_tur_recycle
Create Date: 2026-05-14

"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260514_0046_oplog_surface"
down_revision: str | Sequence[str] | None = "20260513_0045_tur_recycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSION_COLUMNS: dict[str, Any] = {
    "id": sa.Integer(),
    "code": sa.String(),
    "name": sa.String(),
    "description": sa.Text(),
    "type": sa.String(),
    "scope": sa.String(),
    "resource": sa.String(),
    "action": sa.String(),
    "parent_id": sa.Integer(),
    "sort_order": sa.Integer(),
    "icon": sa.String(),
    "path": sa.String(),
    "component": sa.String(),
    "hidden": sa.Boolean(),
    "is_enabled": sa.Boolean(),
    "is_deleted": sa.Boolean(),
    "created_at": sa.DateTime(),
    "updated_at": sa.DateTime(),
    "deleted_at": sa.DateTime(),
    "delete_level": sa.String(),
    "recycle_stage": sa.String(),
    "promoted_to_global_at": sa.DateTime(),
    "permission_id": sa.Integer(),
}

RESTORED_SURFACES = (
    {
        "scope": "admin",
        "parent_code": "menu:admin.logs",
        "menu": {
            "code": "menu:admin.operation_log",
            "name": "menu.admin.operation_log",
            "type": "menu",
            "scope": "admin",
            "resource": "menu",
            "action": "admin.operation_log",
            "description": "",
            "sort_order": 10,
            "icon": "lucide:file-text",
            "path": "/system/operation-logs",
            "component": "admin/system/operation-logs/index",
            "hidden": False,
        },
        "operations": (
            {
                "code": "operation_log:list",
                "name": "action.operation_log.list",
                "type": "operation",
                "scope": "admin",
                "resource": "operation_log",
                "action": "list",
                "description": "",
                "sort_order": 10,
                "hidden": False,
            },
            {
                "code": "operation_log:detail",
                "name": "action.operation_log.detail",
                "type": "operation",
                "scope": "admin",
                "resource": "operation_log",
                "action": "detail",
                "description": "",
                "sort_order": 20,
                "hidden": False,
            },
            {
                "code": "operation_log:delete",
                "name": "action.operation_log.delete",
                "type": "operation",
                "scope": "admin",
                "resource": "operation_log",
                "action": "delete",
                "description": "",
                "sort_order": 40,
                "hidden": False,
            },
        ),
        "link_tables": (
            ("admin_role_permissions", "role_id"),
            ("admin_org_node_permissions", "org_node_id"),
        ),
    },
    {
        "scope": "tenant",
        "parent_code": "menu:tenant.logs",
        "menu": {
            "code": "menu:tenant.operation_log",
            "name": "menu.tenant.operation_log",
            "type": "menu",
            "scope": "tenant",
            "resource": "menu",
            "action": "tenant.operation_log",
            "description": "",
            "sort_order": 10,
            "icon": "lucide:file-text",
            "path": "/system/operation-logs",
            "component": "tenant/system/operation-logs/index",
            "hidden": False,
        },
        "operations": (
            {
                "code": "operation_log:list",
                "name": "action.operation_log.list",
                "type": "operation",
                "scope": "tenant",
                "resource": "operation_log",
                "action": "list",
                "description": "",
                "sort_order": 10,
                "hidden": False,
            },
            {
                "code": "operation_log:detail",
                "name": "action.operation_log.detail",
                "type": "operation",
                "scope": "tenant",
                "resource": "operation_log",
                "action": "detail",
                "description": "",
                "sort_order": 20,
                "hidden": False,
            },
        ),
        "link_tables": (
            ("tenant_plan_permissions", "plan_id"),
            ("tenant_admin_role_permissions", "role_id"),
            ("tenant_org_node_permissions", "org_node_id"),
        ),
    },
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _has_table(bind: sa.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _columns(bind: sa.Connection, table_name: str) -> set[str]:
    if not _has_table(bind, table_name):
        return set()
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _table(table_name: str, columns: set[str]) -> sa.TableClause:
    return sa.table(
        table_name,
        *(sa.column(name, PERMISSION_COLUMNS.get(name)) for name in columns),
    )


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


def _payload_for_columns(
    payload: dict[str, Any],
    columns: set[str],
    *,
    parent_id: int | None,
    include_created_at: bool,
) -> dict[str, Any]:
    values = {key: value for key, value in payload.items() if key in columns}
    if "parent_id" in columns:
        values["parent_id"] = parent_id
    if "is_enabled" in columns:
        values["is_enabled"] = True
    if "is_deleted" in columns:
        values["is_deleted"] = False
    if "deleted_at" in columns:
        values["deleted_at"] = None
    if "delete_level" in columns:
        values["delete_level"] = None
    if "recycle_stage" in columns:
        values["recycle_stage"] = None
    if "promoted_to_global_at" in columns:
        values["promoted_to_global_at"] = None
    if "updated_at" in columns:
        values["updated_at"] = _now()
    if include_created_at and "created_at" in columns:
        values["created_at"] = _now()
    return values


def _ensure_permission(
    bind: sa.Connection,
    permissions: sa.TableClause,
    columns: set[str],
    payload: dict[str, Any],
    *,
    parent_id: int | None,
) -> int:
    existing_id = _permission_id_by_code(
        bind,
        permissions,
        scope=str(payload["scope"]),
        code=str(payload["code"]),
    )
    if existing_id is not None:
        values = _payload_for_columns(
            payload,
            columns,
            parent_id=parent_id,
            include_created_at=False,
        )
        bind.execute(
            sa.update(permissions)
            .where(permissions.c.id == existing_id)
            .values(**values)
        )
        return existing_id

    values = _payload_for_columns(
        payload,
        columns,
        parent_id=parent_id,
        include_created_at=True,
    )
    bind.execute(sa.insert(permissions).values(**values))
    restored_id = _permission_id_by_code(
        bind,
        permissions,
        scope=str(payload["scope"]),
        code=str(payload["code"]),
    )
    if restored_id is None:
        raise RuntimeError(f"Failed to restore permission {payload['code']}")
    return restored_id


def _grant_from_parent_link(
    bind: sa.Connection,
    *,
    table_name: str,
    owner_column: str,
    parent_permission_id: int,
    restored_permission_ids: Sequence[int],
) -> None:
    columns = _columns(bind, table_name)
    if owner_column not in columns or "permission_id" not in columns:
        return

    link_table = _table(table_name, columns)
    owner_rows = bind.execute(
        sa.select(link_table.c[owner_column]).where(
            link_table.c.permission_id == parent_permission_id
        )
    ).all()
    owner_ids = sorted({int(row[0]) for row in owner_rows if row[0] is not None})
    if not owner_ids:
        return

    existing_pairs = {
        (int(row[0]), int(row[1]))
        for row in bind.execute(
            sa.select(link_table.c[owner_column], link_table.c.permission_id).where(
                link_table.c[owner_column].in_(owner_ids),
                link_table.c.permission_id.in_(list(restored_permission_ids)),
            )
        ).all()
    }
    inserts = [
        {owner_column: owner_id, "permission_id": permission_id}
        for owner_id in owner_ids
        for permission_id in restored_permission_ids
        if (owner_id, permission_id) not in existing_pairs
    ]
    if inserts:
        bind.execute(sa.insert(link_table), inserts)


def _restore_surface(
    bind: sa.Connection,
    permissions: sa.TableClause,
    columns: set[str],
    surface: dict[str, Any],
) -> None:
    parent_id = _permission_id_by_code(
        bind,
        permissions,
        scope=str(surface["scope"]),
        code=str(surface["parent_code"]),
    )
    if parent_id is None:
        return

    menu_id = _ensure_permission(
        bind,
        permissions,
        columns,
        surface["menu"],
        parent_id=parent_id,
    )
    restored_ids = [menu_id]
    for operation in surface["operations"]:
        restored_ids.append(
            _ensure_permission(
                bind,
                permissions,
                columns,
                operation,
                parent_id=menu_id,
            )
        )

    for table_name, owner_column in surface["link_tables"]:
        _grant_from_parent_link(
            bind,
            table_name=table_name,
            owner_column=owner_column,
            parent_permission_id=parent_id,
            restored_permission_ids=restored_ids,
        )


def upgrade() -> None:
    bind = op.get_bind()
    permission_columns = _columns(bind, "permissions")
    required_columns = {"id", "code", "scope", "name", "type", "resource", "action"}
    if not required_columns.issubset(permission_columns):
        return

    permissions = _table("permissions", permission_columns)
    for surface in RESTORED_SURFACES:
        _restore_surface(bind, permissions, permission_columns, surface)


def downgrade() -> None:
    # 中文: 恢复迁移不主动删除权限；当前代码声明和启动同步是最终权限来源。
    # EN: The restore migration does not delete permissions; current code declarations and startup sync remain authoritative.
    pass
