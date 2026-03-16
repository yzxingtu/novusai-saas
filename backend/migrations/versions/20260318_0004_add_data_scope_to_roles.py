"""add data_scope and custom_dept_ids to role tables

Revision ID: 20260318_0004_data_scope
Revises: 20260318_0003_trace_id
Create Date: 2026-03-18 00:00:00.000000

为 admin_roles 和 tenant_admin_roles 增加数据权限字段。
Add data permission fields to admin_roles and tenant_admin_roles.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260318_0004_data_scope"
down_revision = "20260318_0003_trace_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # admin_roles: data_scope, custom_dept_ids
    op.add_column(
        "admin_roles",
        sa.Column(
            "data_scope",
            sa.String(20),
            nullable=False,
            server_default="self",
            comment="数据范围: all/dept_children/dept_only/self/custom",
        ),
    )
    op.add_column(
        "admin_roles",
        sa.Column(
            "custom_dept_ids",
            sa.JSON(),
            nullable=True,
            comment="自定义部门 ID 列表 [1,2,3]",
        ),
    )
    op.create_index(
        "ix_admin_roles_data_scope",
        "admin_roles",
        ["data_scope"],
        unique=False,
    )

    # tenant_admin_roles: data_scope, custom_dept_ids
    op.add_column(
        "tenant_admin_roles",
        sa.Column(
            "data_scope",
            sa.String(20),
            nullable=False,
            server_default="self",
            comment="数据范围: all/dept_children/dept_only/self/custom",
        ),
    )
    op.add_column(
        "tenant_admin_roles",
        sa.Column(
            "custom_dept_ids",
            sa.JSON(),
            nullable=True,
            comment="自定义部门 ID 列表 [1,2,3]",
        ),
    )
    op.create_index(
        "ix_tenant_admin_roles_data_scope",
        "tenant_admin_roles",
        ["data_scope"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_admin_roles_data_scope", table_name="tenant_admin_roles")
    op.drop_column("tenant_admin_roles", "custom_dept_ids")
    op.drop_column("tenant_admin_roles", "data_scope")
    op.drop_index("ix_admin_roles_data_scope", table_name="admin_roles")
    op.drop_column("admin_roles", "custom_dept_ids")
    op.drop_column("admin_roles", "data_scope")
