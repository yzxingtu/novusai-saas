"""add tenant_user_roles table and tenant_user role_id fk

Creates:
1. tenant_user_roles table - 企业用户角色表
2. tenant_user_role_permissions association table - 角色权限关联表
3. role_id FK column on tenant_users table

Revision ID: 20260307_user_roles
Revises: 20260307_router_zh
Create Date: 2026-03-07 22:00:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260307_user_roles"
down_revision: str = "20260307_router_zh"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # 1. 创建 tenant_user_roles 表
    op.create_table(
        "tenant_user_roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey(
                "tenants.id", ondelete="CASCADE", name="fk_tenant_user_roles_tenant_id"
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(50), nullable=False, comment="角色名称"),
        sa.Column("code", sa.String(50), nullable=False, comment="角色代码"),
        sa.Column("description", sa.Text(), nullable=True, comment="角色描述"),
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="是否系统内置",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="是否启用",
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="排序",
        ),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "deleted_at", sa.DateTime(), nullable=True, comment="删除时间 / Deleted at"
        ),
        sa.Column(
            "delete_level",
            sa.String(length=20),
            nullable=True,
            comment="删除侧别 / Delete scope: tenant/admin",
        ),
        sa.Column(
            "recycle_stage",
            sa.String(length=20),
            nullable=True,
            comment="回收站阶段 / Recycle stage: module/global",
        ),
        sa.Column(
            "promoted_to_global_at",
            sa.DateTime(),
            nullable=True,
            comment="进入总回收站时间 / Promoted to global recycle bin at",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenant_user_roles_code", "tenant_user_roles", ["code"])
    op.create_index(
        "ix_tenant_user_roles_recycle_stage", "tenant_user_roles", ["recycle_stage"]
    )
    op.create_index(
        "ix_tenant_user_roles_tenant_id", "tenant_user_roles", ["tenant_id"]
    )

    # 2. 创建 tenant_user_role_permissions 关联表
    op.create_table(
        "tenant_user_role_permissions",
        sa.Column(
            "role_id",
            sa.Integer(),
            sa.ForeignKey(
                "tenant_user_roles.id", ondelete="CASCADE", name="fk_turp_role_id"
            ),
            primary_key=True,
        ),
        sa.Column(
            "permission_id",
            sa.Integer(),
            sa.ForeignKey(
                "permissions.id", ondelete="CASCADE", name="fk_turp_permission_id"
            ),
            primary_key=True,
        ),
    )

    # 3. 为 tenant_users 表添加 role_id 列
    op.add_column(
        "tenant_users",
        sa.Column(
            "role_id",
            sa.Integer(),
            sa.ForeignKey(
                "tenant_user_roles.id",
                ondelete="SET NULL",
                name="fk_tenant_users_role_id",
            ),
            nullable=True,
            comment="用户角色 ID",
        ),
    )
    op.create_index("ix_tenant_users_role_id", "tenant_users", ["role_id"])


def downgrade() -> None:
    # 3. 移除 tenant_users.role_id
    op.drop_index("ix_tenant_users_role_id", table_name="tenant_users")
    op.drop_constraint("fk_tenant_users_role_id", "tenant_users", type_="foreignkey")
    op.drop_column("tenant_users", "role_id")

    # 2. 删除关联表
    op.drop_table("tenant_user_role_permissions")

    # 1. 删除角色表
    op.drop_index("ix_tenant_user_roles_tenant_id", table_name="tenant_user_roles")
    op.drop_index("ix_tenant_user_roles_recycle_stage", table_name="tenant_user_roles")
    op.drop_index("ix_tenant_user_roles_code", table_name="tenant_user_roles")
    op.drop_table("tenant_user_roles")
