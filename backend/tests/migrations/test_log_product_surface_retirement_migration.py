"""Test type: structural / behavioral.

中文: 覆盖退役日志产品页的 RBAC 清理迁移。
EN: Covers the RBAC cleanup migration for retired log product pages.
中文: 使用静态源码检查和内存 SQLAlchemy 表验证迁移行为。
EN: Uses static source inspection and in-memory SQLAlchemy tables to validate
migration behavior.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "versions"
    / "20260509_0041_retire_log_pages.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "test_log_product_surface_retirement_migration_module",
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
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(255), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("resource", sa.String(255), nullable=False),
        sa.Column("parent_id", sa.Integer, nullable=True),
    )
    admin_role_permissions = sa.Table(
        "admin_role_permissions",
        metadata,
        sa.Column("role_id", sa.Integer, nullable=False),
        sa.Column("permission_id", sa.Integer, nullable=False),
    )
    tenant_admin_role_permissions = sa.Table(
        "tenant_admin_role_permissions",
        metadata,
        sa.Column("role_id", sa.Integer, nullable=False),
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
    ai_action_logs = sa.Table(
        "ai_action_logs",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
    )
    sa.Index("ix_operation_logs_trace_id", operation_logs.c.trace_id)
    sa.Index("ix_ai_action_logs_trace_id", ai_action_logs.c.trace_id)
    metadata.create_all(conn)
    return {
        "permissions": permissions,
        "admin_role_permissions": admin_role_permissions,
        "tenant_admin_role_permissions": tenant_admin_role_permissions,
        "tenant_plan_permissions": tenant_plan_permissions,
        "operation_logs": operation_logs,
        "ai_action_logs": ai_action_logs,
    }


def test_log_product_surface_retirement_migration_only_cleans_rbac_rows() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260509_0041_log_pages"' in source
    assert (
        'down_revision: str | Sequence[str] | None = "20260509_0040_drop_ledgers"'
        in source
    )
    assert "op.drop_table" not in source
    assert "op.drop_index" not in source
    assert "operation_logs" not in source
    assert "ai_action_logs" not in source
    assert "sa.delete" in source


def test_log_product_surface_retirement_migration_preserves_audit_tables(
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
                    "scope": "admin",
                    "resource": "menu",
                    "parent_id": None,
                },
                {
                    "id": 2,
                    "code": "menu:tenant.logs",
                    "scope": "tenant",
                    "resource": "menu",
                    "parent_id": None,
                },
                {
                    "id": 3,
                    "code": "menu:tenant.ai_analytics",
                    "scope": "tenant",
                    "resource": "menu",
                    "parent_id": None,
                },
                {
                    "id": 4,
                    "code": "menu:admin.operation_log",
                    "scope": "admin",
                    "resource": "menu",
                    "parent_id": 1,
                },
                {
                    "id": 5,
                    "code": "operation_log:list",
                    "scope": "admin",
                    "resource": "operation_log",
                    "parent_id": 4,
                },
                {
                    "id": 6,
                    "code": "menu:tenant.operation_log",
                    "scope": "tenant",
                    "resource": "menu",
                    "parent_id": 2,
                },
                {
                    "id": 7,
                    "code": "operation_log:list",
                    "scope": "tenant",
                    "resource": "operation_log",
                    "parent_id": 6,
                },
                {
                    "id": 8,
                    "code": "menu:tenant.ai_action_log",
                    "scope": "tenant",
                    "resource": "menu",
                    "parent_id": 3,
                },
                {
                    "id": 9,
                    "code": "ai_action_log:stats",
                    "scope": "tenant",
                    "resource": "ai_action_log",
                    "parent_id": 8,
                },
                {
                    "id": 10,
                    "code": "system_log:list",
                    "scope": "admin",
                    "resource": "system_log",
                    "parent_id": 4,
                },
                {
                    "id": 11,
                    "code": "ai_call_log:list",
                    "scope": "tenant",
                    "resource": "ai_call_log",
                    "parent_id": 3,
                },
            ],
        )
        conn.execute(
            tables["admin_role_permissions"].insert(),
            [
                {"role_id": 1, "permission_id": 5},
                {"role_id": 1, "permission_id": 10},
            ],
        )
        conn.execute(
            tables["tenant_admin_role_permissions"].insert(),
            [
                {"role_id": 2, "permission_id": 7},
                {"role_id": 2, "permission_id": 11},
            ],
        )
        conn.execute(
            tables["tenant_plan_permissions"].insert(),
            [
                {"plan_id": 3, "permission_id": 9},
                {"plan_id": 3, "permission_id": 11},
            ],
        )
        conn.execute(tables["operation_logs"].insert(), [{"id": 1, "trace_id": "t1"}])
        conn.execute(tables["ai_action_logs"].insert(), [{"id": 1, "trace_id": "t1"}])

        monkeypatch.setattr(module.op, "get_bind", lambda: conn)
        module.upgrade()

        remaining_permissions = {
            row["id"]: row
            for row in conn.execute(sa.select(permissions)).mappings().all()
        }
        admin_links = [
            dict(row)
            for row in conn.execute(
                sa.select(tables["admin_role_permissions"])
            ).mappings()
        ]
        tenant_admin_links = [
            dict(row)
            for row in conn.execute(
                sa.select(tables["tenant_admin_role_permissions"])
            ).mappings()
        ]
        tenant_plan_links = [
            dict(row)
            for row in conn.execute(
                sa.select(tables["tenant_plan_permissions"])
            ).mappings()
        ]
        inspector = sa.inspect(conn)
        has_operation_logs = inspector.has_table("operation_logs")
        has_ai_action_logs = inspector.has_table("ai_action_logs")
        operation_log_indexes = {
            index["name"] for index in inspector.get_indexes("operation_logs")
        }
        ai_action_log_indexes = {
            index["name"] for index in inspector.get_indexes("ai_action_logs")
        }

    assert set(remaining_permissions) == {1, 2, 3, 10, 11}
    assert remaining_permissions[10]["parent_id"] == 1
    assert admin_links == [{"role_id": 1, "permission_id": 10}]
    assert tenant_admin_links == [{"role_id": 2, "permission_id": 11}]
    assert tenant_plan_links == [{"plan_id": 3, "permission_id": 11}]
    assert has_operation_logs
    assert has_ai_action_logs
    assert operation_log_indexes == {"ix_operation_logs_trace_id"}
    assert ai_action_log_indexes == {"ix_ai_action_logs_trace_id"}
