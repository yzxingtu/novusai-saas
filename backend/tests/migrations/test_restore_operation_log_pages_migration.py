"""Test type: structural / behavioral.

中文: 覆盖恢复操作日志产品页的 RBAC 回补迁移。
EN: Covers the RBAC restoration migration for operation log product pages.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "versions"
    / "20260514_0046_restore_operation_log_pages.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "test_restore_operation_log_pages_migration_module",
        MIGRATION,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_tables(conn) -> dict[str, sa.Table]:
    metadata = sa.MetaData()
    permissions = sa.Table(
        "permissions",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("resource", sa.String(255), nullable=False),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("parent_id", sa.Integer, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, default=0),
        sa.Column("icon", sa.String(255), nullable=True),
        sa.Column("path", sa.String(255), nullable=True),
        sa.Column("component", sa.String(255), nullable=True),
        sa.Column("hidden", sa.Boolean, nullable=False, default=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False, default=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, default=False),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    admin_role_permissions = sa.Table(
        "admin_role_permissions",
        metadata,
        sa.Column("role_id", sa.Integer, nullable=False),
        sa.Column("permission_id", sa.Integer, nullable=False),
    )
    admin_org_node_permissions = sa.Table(
        "admin_org_node_permissions",
        metadata,
        sa.Column("org_node_id", sa.Integer, nullable=False),
        sa.Column("permission_id", sa.Integer, nullable=False),
    )
    tenant_admin_role_permissions = sa.Table(
        "tenant_admin_role_permissions",
        metadata,
        sa.Column("role_id", sa.Integer, nullable=False),
        sa.Column("permission_id", sa.Integer, nullable=False),
    )
    tenant_org_node_permissions = sa.Table(
        "tenant_org_node_permissions",
        metadata,
        sa.Column("org_node_id", sa.Integer, nullable=False),
        sa.Column("permission_id", sa.Integer, nullable=False),
    )
    tenant_plan_permissions = sa.Table(
        "tenant_plan_permissions",
        metadata,
        sa.Column("plan_id", sa.Integer, nullable=False),
        sa.Column("permission_id", sa.Integer, nullable=False),
    )
    operation_logs = sa.Table(
        "operation_logs",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
    )
    sa.Index("ix_operation_logs_trace_id", operation_logs.c.trace_id)
    metadata.create_all(conn)
    return {
        "permissions": permissions,
        "admin_role_permissions": admin_role_permissions,
        "admin_org_node_permissions": admin_org_node_permissions,
        "tenant_admin_role_permissions": tenant_admin_role_permissions,
        "tenant_org_node_permissions": tenant_org_node_permissions,
        "tenant_plan_permissions": tenant_plan_permissions,
        "operation_logs": operation_logs,
    }


def test_restore_operation_log_pages_migration_rehydrates_rbac_links(
    monkeypatch,
) -> None:
    module = _load_migration_module()
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as conn:
        tables = _create_tables(conn)
        permissions = tables["permissions"]
        conn.execute(
            permissions.insert(),
            [
                {
                    "id": 1,
                    "code": "menu:admin.logs",
                    "name": "menu.admin.logs",
                    "type": "menu",
                    "scope": "admin",
                    "resource": "menu",
                    "action": "admin.logs",
                    "sort_order": 10,
                    "hidden": False,
                    "is_enabled": True,
                    "is_deleted": False,
                },
                {
                    "id": 2,
                    "code": "menu:tenant.logs",
                    "name": "menu.tenant.logs",
                    "type": "menu",
                    "scope": "tenant",
                    "resource": "menu",
                    "action": "tenant.logs",
                    "sort_order": 10,
                    "hidden": False,
                    "is_enabled": True,
                    "is_deleted": False,
                },
            ],
        )
        conn.execute(
            tables["admin_role_permissions"].insert(),
            [{"role_id": 11, "permission_id": 1}],
        )
        conn.execute(
            tables["admin_org_node_permissions"].insert(),
            [{"org_node_id": 12, "permission_id": 1}],
        )
        conn.execute(
            tables["tenant_plan_permissions"].insert(),
            [{"plan_id": 21, "permission_id": 2}],
        )
        conn.execute(
            tables["tenant_admin_role_permissions"].insert(),
            [{"role_id": 22, "permission_id": 2}],
        )
        conn.execute(
            tables["tenant_org_node_permissions"].insert(),
            [{"org_node_id": 23, "permission_id": 2}],
        )
        conn.execute(tables["operation_logs"].insert(), [{"id": 1, "trace_id": "t1"}])

        monkeypatch.setattr(module.op, "get_bind", lambda: conn)
        module.upgrade()
        module.upgrade()

        permission_rows = conn.execute(sa.select(permissions)).mappings().all()
        permission_by_scope_code = {
            (row["scope"], row["code"]): row for row in permission_rows
        }
        admin_role_links = {
            (row["role_id"], row["permission_id"])
            for row in conn.execute(
                sa.select(tables["admin_role_permissions"])
            ).mappings()
        }
        admin_org_links = {
            (row["org_node_id"], row["permission_id"])
            for row in conn.execute(
                sa.select(tables["admin_org_node_permissions"])
            ).mappings()
        }
        tenant_plan_links = {
            (row["plan_id"], row["permission_id"])
            for row in conn.execute(
                sa.select(tables["tenant_plan_permissions"])
            ).mappings()
        }
        tenant_role_links = {
            (row["role_id"], row["permission_id"])
            for row in conn.execute(
                sa.select(tables["tenant_admin_role_permissions"])
            ).mappings()
        }
        tenant_org_links = {
            (row["org_node_id"], row["permission_id"])
            for row in conn.execute(
                sa.select(tables["tenant_org_node_permissions"])
            ).mappings()
        }
        operation_log_count = conn.execute(
            sa.select(sa.func.count()).select_from(tables["operation_logs"])
        ).scalar_one()

    admin_menu = permission_by_scope_code[("admin", "menu:admin.operation_log")]
    admin_list = permission_by_scope_code[("admin", "operation_log:list")]
    admin_detail = permission_by_scope_code[("admin", "operation_log:detail")]
    admin_delete = permission_by_scope_code[("admin", "operation_log:delete")]
    tenant_menu = permission_by_scope_code[("tenant", "menu:tenant.operation_log")]
    tenant_list = permission_by_scope_code[("tenant", "operation_log:list")]
    tenant_detail = permission_by_scope_code[("tenant", "operation_log:detail")]

    admin_menu_id = admin_menu["id"]
    admin_list_id = admin_list["id"]
    admin_detail_id = admin_detail["id"]
    admin_delete_id = admin_delete["id"]
    tenant_menu_id = tenant_menu["id"]
    tenant_list_id = tenant_list["id"]
    tenant_detail_id = tenant_detail["id"]

    assert admin_menu["parent_id"] == 1
    assert tenant_menu["parent_id"] == 2
    assert admin_list["parent_id"] == admin_menu_id
    assert tenant_list["parent_id"] == tenant_menu_id
    assert {
        (11, admin_menu_id),
        (11, admin_list_id),
        (11, admin_detail_id),
        (11, admin_delete_id),
    }.issubset(admin_role_links)
    assert {
        (12, admin_menu_id),
        (12, admin_list_id),
        (12, admin_detail_id),
        (12, admin_delete_id),
    }.issubset(admin_org_links)
    assert {
        (21, tenant_menu_id),
        (21, tenant_list_id),
        (21, tenant_detail_id),
    }.issubset(tenant_plan_links)
    assert {
        (22, tenant_menu_id),
        (22, tenant_list_id),
        (22, tenant_detail_id),
    }.issubset(tenant_role_links)
    assert {
        (23, tenant_menu_id),
        (23, tenant_list_id),
        (23, tenant_detail_id),
    }.issubset(tenant_org_links)
    assert operation_log_count == 1


def test_restore_operation_log_pages_migration_keeps_log_tables_static() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260514_0046_oplog_surface"' in source
    assert (
        'down_revision: str | Sequence[str] | None = "20260513_0045_tur_recycle"'
        in source
    )
    assert "op.drop_table" not in source
    assert "op.drop_index" not in source
    assert "op.create_table" not in source
    assert "op.create_index" not in source
