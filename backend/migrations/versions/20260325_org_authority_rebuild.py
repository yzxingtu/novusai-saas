"""rebuild organization authority foundation

Revision ID: 20260325_org_authority_rebuild
Revises: 20260325_skill_arch_foundation
Create Date: 2026-03-25 00:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "20260325_org_authority_rebuild"
down_revision = "20260325_skill_arch_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_org_nodes",
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("path", sa.String(length=500), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("type", sa.String(length=20), nullable=False, server_default="department"),
        sa.Column("allow_members", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("leader_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["leader_id"], ["admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_id"], ["admin_org_nodes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_admin_org_nodes_code"), "admin_org_nodes", ["code"], unique=False)
    op.create_index(op.f("ix_admin_org_nodes_id"), "admin_org_nodes", ["id"], unique=False)
    op.create_index(op.f("ix_admin_org_nodes_is_deleted"), "admin_org_nodes", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_admin_org_nodes_leader_id"), "admin_org_nodes", ["leader_id"], unique=False)
    op.create_index(op.f("ix_admin_org_nodes_parent_id"), "admin_org_nodes", ["parent_id"], unique=False)
    op.create_index(op.f("ix_admin_org_nodes_path"), "admin_org_nodes", ["path"], unique=False)
    op.create_index(op.f("ix_admin_org_nodes_recycle_stage"), "admin_org_nodes", ["recycle_stage"], unique=False)
    op.create_index(op.f("ix_admin_org_nodes_type"), "admin_org_nodes", ["type"], unique=False)

    op.create_table(
        "admin_org_scope_policies",
        sa.Column("org_node_id", sa.Integer(), nullable=False),
        sa.Column("scope_mode", sa.String(length=20), nullable=False, server_default="dept_children"),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["org_node_id"], ["admin_org_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_node_id"),
    )
    op.create_index(op.f("ix_admin_org_scope_policies_id"), "admin_org_scope_policies", ["id"], unique=False)
    op.create_index(op.f("ix_admin_org_scope_policies_is_deleted"), "admin_org_scope_policies", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_admin_org_scope_policies_org_node_id"), "admin_org_scope_policies", ["org_node_id"], unique=True)
    op.create_index(op.f("ix_admin_org_scope_policies_recycle_stage"), "admin_org_scope_policies", ["recycle_stage"], unique=False)
    op.create_index(op.f("ix_admin_org_scope_policies_scope_mode"), "admin_org_scope_policies", ["scope_mode"], unique=False)

    op.create_table(
        "admin_org_scope_targets",
        sa.Column("policy_id", sa.Integer(), nullable=False),
        sa.Column("target_org_node_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["policy_id"], ["admin_org_scope_policies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_org_node_id"], ["admin_org_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_admin_org_scope_targets_id"), "admin_org_scope_targets", ["id"], unique=False)
    op.create_index(op.f("ix_admin_org_scope_targets_is_deleted"), "admin_org_scope_targets", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_admin_org_scope_targets_policy_id"), "admin_org_scope_targets", ["policy_id"], unique=False)
    op.create_index(op.f("ix_admin_org_scope_targets_recycle_stage"), "admin_org_scope_targets", ["recycle_stage"], unique=False)
    op.create_index(op.f("ix_admin_org_scope_targets_target_org_node_id"), "admin_org_scope_targets", ["target_org_node_id"], unique=False)

    op.create_table(
        "tenant_org_nodes",
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("path", sa.String(length=500), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("type", sa.String(length=20), nullable=False, server_default="department"),
        sa.Column("allow_members", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("leader_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["leader_id"], ["tenant_admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_id"], ["tenant_org_nodes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tenant_org_nodes_code"), "tenant_org_nodes", ["code"], unique=False)
    op.create_index(op.f("ix_tenant_org_nodes_id"), "tenant_org_nodes", ["id"], unique=False)
    op.create_index(op.f("ix_tenant_org_nodes_is_deleted"), "tenant_org_nodes", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_tenant_org_nodes_leader_id"), "tenant_org_nodes", ["leader_id"], unique=False)
    op.create_index(op.f("ix_tenant_org_nodes_parent_id"), "tenant_org_nodes", ["parent_id"], unique=False)
    op.create_index(op.f("ix_tenant_org_nodes_path"), "tenant_org_nodes", ["path"], unique=False)
    op.create_index(op.f("ix_tenant_org_nodes_recycle_stage"), "tenant_org_nodes", ["recycle_stage"], unique=False)
    op.create_index(op.f("ix_tenant_org_nodes_tenant_id"), "tenant_org_nodes", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_tenant_org_nodes_type"), "tenant_org_nodes", ["type"], unique=False)

    op.create_table(
        "tenant_org_scope_policies",
        sa.Column("org_node_id", sa.Integer(), nullable=False),
        sa.Column("scope_mode", sa.String(length=20), nullable=False, server_default="dept_children"),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["org_node_id"], ["tenant_org_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_node_id"),
    )
    op.create_index(op.f("ix_tenant_org_scope_policies_id"), "tenant_org_scope_policies", ["id"], unique=False)
    op.create_index(op.f("ix_tenant_org_scope_policies_is_deleted"), "tenant_org_scope_policies", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_tenant_org_scope_policies_org_node_id"), "tenant_org_scope_policies", ["org_node_id"], unique=True)
    op.create_index(op.f("ix_tenant_org_scope_policies_recycle_stage"), "tenant_org_scope_policies", ["recycle_stage"], unique=False)
    op.create_index(op.f("ix_tenant_org_scope_policies_scope_mode"), "tenant_org_scope_policies", ["scope_mode"], unique=False)
    op.create_index(op.f("ix_tenant_org_scope_policies_tenant_id"), "tenant_org_scope_policies", ["tenant_id"], unique=False)

    op.create_table(
        "tenant_org_scope_targets",
        sa.Column("policy_id", sa.Integer(), nullable=False),
        sa.Column("target_org_node_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["policy_id"], ["tenant_org_scope_policies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_org_node_id"], ["tenant_org_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tenant_org_scope_targets_id"), "tenant_org_scope_targets", ["id"], unique=False)
    op.create_index(op.f("ix_tenant_org_scope_targets_is_deleted"), "tenant_org_scope_targets", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_tenant_org_scope_targets_policy_id"), "tenant_org_scope_targets", ["policy_id"], unique=False)
    op.create_index(op.f("ix_tenant_org_scope_targets_recycle_stage"), "tenant_org_scope_targets", ["recycle_stage"], unique=False)
    op.create_index(op.f("ix_tenant_org_scope_targets_target_org_node_id"), "tenant_org_scope_targets", ["target_org_node_id"], unique=False)
    op.create_index(op.f("ix_tenant_org_scope_targets_tenant_id"), "tenant_org_scope_targets", ["tenant_id"], unique=False)

    op.add_column("admins", sa.Column("org_node_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_admins_org_node_id"), "admins", ["org_node_id"], unique=False)
    op.create_foreign_key(
        "fk_admins_org_node_id_admin_org_nodes",
        "admins",
        "admin_org_nodes",
        ["org_node_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("tenant_admins", sa.Column("org_node_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_tenant_admins_org_node_id"), "tenant_admins", ["org_node_id"], unique=False)
    op.create_foreign_key(
        "fk_tenant_admins_org_node_id_tenant_org_nodes",
        "tenant_admins",
        "tenant_org_nodes",
        ["org_node_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("tenant_users", sa.Column("org_node_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_tenant_users_org_node_id"), "tenant_users", ["org_node_id"], unique=False)
    op.create_foreign_key(
        "fk_tenant_users_org_node_id_tenant_org_nodes",
        "tenant_users",
        "tenant_org_nodes",
        ["org_node_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute(sa.text(
        """
        INSERT INTO admin_org_nodes (
            id, name, code, description, is_system, is_active, sort_order,
            parent_id, path, level, type, allow_members, leader_id,
            created_at, updated_at, is_deleted, deleted_at, delete_level,
            recycle_stage, promoted_to_global_at
        )
        SELECT
            id, name, code, description, is_system, is_active, sort_order,
            parent_id, path, level, COALESCE(type, 'department'), allow_members, leader_id,
            created_at, updated_at, is_deleted, deleted_at, delete_level,
            recycle_stage, promoted_to_global_at
        FROM admin_roles
        ON CONFLICT (id) DO NOTHING
        """
    ))
    op.execute(sa.text(
        """
        INSERT INTO admin_org_scope_policies (
            id, org_node_id, scope_mode, created_at, updated_at,
            is_deleted, deleted_at, delete_level, recycle_stage, promoted_to_global_at
        )
        SELECT
            id, id, COALESCE(data_scope, 'dept_children'), created_at, updated_at,
            is_deleted, deleted_at, delete_level, recycle_stage, promoted_to_global_at
        FROM admin_roles
        ON CONFLICT (id) DO NOTHING
        """
    ))
    op.execute(sa.text(
        """
        INSERT INTO admin_org_scope_targets (
            policy_id, target_org_node_id, created_at, updated_at,
            is_deleted, deleted_at, delete_level, recycle_stage, promoted_to_global_at
        )
        SELECT
            ar.id,
            CAST(target.value AS INTEGER),
            ar.created_at,
            ar.updated_at,
            ar.is_deleted,
            ar.deleted_at,
            ar.delete_level,
            ar.recycle_stage,
            ar.promoted_to_global_at
        FROM admin_roles ar
        CROSS JOIN LATERAL json_array_elements_text(COALESCE(ar.custom_dept_ids::json, '[]'::json)) AS target(value)
        WHERE NOT EXISTS (
            SELECT 1 FROM admin_org_scope_targets t
            WHERE t.policy_id = ar.id AND t.target_org_node_id = CAST(target.value AS INTEGER)
        )
        """
    ))
    op.execute(sa.text("UPDATE admins SET org_node_id = role_id WHERE role_id IS NOT NULL"))

    op.execute(sa.text(
        """
        INSERT INTO tenant_org_nodes (
            id, tenant_id, name, code, description, is_system, is_active, sort_order,
            parent_id, path, level, type, allow_members, leader_id,
            created_at, updated_at, is_deleted, deleted_at, delete_level,
            recycle_stage, promoted_to_global_at
        )
        SELECT
            id, tenant_id, name, code, description, is_system, is_active, sort_order,
            parent_id, path, level, COALESCE(type, 'department'), allow_members, leader_id,
            created_at, updated_at, is_deleted, deleted_at, delete_level,
            recycle_stage, promoted_to_global_at
        FROM tenant_admin_roles
        ON CONFLICT (id) DO NOTHING
        """
    ))
    op.execute(sa.text(
        """
        INSERT INTO tenant_org_scope_policies (
            id, tenant_id, org_node_id, scope_mode, created_at, updated_at,
            is_deleted, deleted_at, delete_level, recycle_stage, promoted_to_global_at
        )
        SELECT
            id, tenant_id, id, COALESCE(data_scope, 'dept_children'), created_at, updated_at,
            is_deleted, deleted_at, delete_level, recycle_stage, promoted_to_global_at
        FROM tenant_admin_roles
        ON CONFLICT (id) DO NOTHING
        """
    ))
    op.execute(sa.text(
        """
        INSERT INTO tenant_org_scope_targets (
            tenant_id, policy_id, target_org_node_id, created_at, updated_at,
            is_deleted, deleted_at, delete_level, recycle_stage, promoted_to_global_at
        )
        SELECT
            tar.tenant_id,
            tar.id,
            CAST(target.value AS INTEGER),
            tar.created_at,
            tar.updated_at,
            tar.is_deleted,
            tar.deleted_at,
            tar.delete_level,
            tar.recycle_stage,
            tar.promoted_to_global_at
        FROM tenant_admin_roles tar
        CROSS JOIN LATERAL json_array_elements_text(COALESCE(tar.custom_dept_ids::json, '[]'::json)) AS target(value)
        WHERE NOT EXISTS (
            SELECT 1 FROM tenant_org_scope_targets t
            WHERE t.policy_id = tar.id AND t.target_org_node_id = CAST(target.value AS INTEGER)
        )
        """
    ))
    op.execute(sa.text("UPDATE tenant_admins SET org_node_id = role_id WHERE role_id IS NOT NULL"))

    op.execute(
        sa.text("SELECT setval(pg_get_serial_sequence('admin_org_nodes', 'id'), COALESCE((SELECT MAX(id) FROM admin_org_nodes), 1), true)")
    )
    op.execute(
        sa.text("SELECT setval(pg_get_serial_sequence('admin_org_scope_policies', 'id'), COALESCE((SELECT MAX(id) FROM admin_org_scope_policies), 1), true)")
    )
    op.execute(
        sa.text("SELECT setval(pg_get_serial_sequence('tenant_org_nodes', 'id'), COALESCE((SELECT MAX(id) FROM tenant_org_nodes), 1), true)")
    )
    op.execute(
        sa.text("SELECT setval(pg_get_serial_sequence('tenant_org_scope_policies', 'id'), COALESCE((SELECT MAX(id) FROM tenant_org_scope_policies), 1), true)")
    )


def downgrade() -> None:
    op.drop_constraint("fk_tenant_users_org_node_id_tenant_org_nodes", "tenant_users", type_="foreignkey")
    op.drop_index(op.f("ix_tenant_users_org_node_id"), table_name="tenant_users")
    op.drop_column("tenant_users", "org_node_id")

    op.drop_constraint("fk_tenant_admins_org_node_id_tenant_org_nodes", "tenant_admins", type_="foreignkey")
    op.drop_index(op.f("ix_tenant_admins_org_node_id"), table_name="tenant_admins")
    op.drop_column("tenant_admins", "org_node_id")

    op.drop_constraint("fk_admins_org_node_id_admin_org_nodes", "admins", type_="foreignkey")
    op.drop_index(op.f("ix_admins_org_node_id"), table_name="admins")
    op.drop_column("admins", "org_node_id")

    op.drop_index(op.f("ix_tenant_org_scope_targets_tenant_id"), table_name="tenant_org_scope_targets")
    op.drop_index(op.f("ix_tenant_org_scope_targets_target_org_node_id"), table_name="tenant_org_scope_targets")
    op.drop_index(op.f("ix_tenant_org_scope_targets_recycle_stage"), table_name="tenant_org_scope_targets")
    op.drop_index(op.f("ix_tenant_org_scope_targets_policy_id"), table_name="tenant_org_scope_targets")
    op.drop_index(op.f("ix_tenant_org_scope_targets_is_deleted"), table_name="tenant_org_scope_targets")
    op.drop_index(op.f("ix_tenant_org_scope_targets_id"), table_name="tenant_org_scope_targets")
    op.drop_table("tenant_org_scope_targets")

    op.drop_index(op.f("ix_tenant_org_scope_policies_tenant_id"), table_name="tenant_org_scope_policies")
    op.drop_index(op.f("ix_tenant_org_scope_policies_scope_mode"), table_name="tenant_org_scope_policies")
    op.drop_index(op.f("ix_tenant_org_scope_policies_recycle_stage"), table_name="tenant_org_scope_policies")
    op.drop_index(op.f("ix_tenant_org_scope_policies_org_node_id"), table_name="tenant_org_scope_policies")
    op.drop_index(op.f("ix_tenant_org_scope_policies_is_deleted"), table_name="tenant_org_scope_policies")
    op.drop_index(op.f("ix_tenant_org_scope_policies_id"), table_name="tenant_org_scope_policies")
    op.drop_table("tenant_org_scope_policies")

    op.drop_index(op.f("ix_tenant_org_nodes_type"), table_name="tenant_org_nodes")
    op.drop_index(op.f("ix_tenant_org_nodes_tenant_id"), table_name="tenant_org_nodes")
    op.drop_index(op.f("ix_tenant_org_nodes_recycle_stage"), table_name="tenant_org_nodes")
    op.drop_index(op.f("ix_tenant_org_nodes_path"), table_name="tenant_org_nodes")
    op.drop_index(op.f("ix_tenant_org_nodes_parent_id"), table_name="tenant_org_nodes")
    op.drop_index(op.f("ix_tenant_org_nodes_leader_id"), table_name="tenant_org_nodes")
    op.drop_index(op.f("ix_tenant_org_nodes_is_deleted"), table_name="tenant_org_nodes")
    op.drop_index(op.f("ix_tenant_org_nodes_id"), table_name="tenant_org_nodes")
    op.drop_index(op.f("ix_tenant_org_nodes_code"), table_name="tenant_org_nodes")
    op.drop_table("tenant_org_nodes")

    op.drop_index(op.f("ix_admin_org_scope_targets_target_org_node_id"), table_name="admin_org_scope_targets")
    op.drop_index(op.f("ix_admin_org_scope_targets_recycle_stage"), table_name="admin_org_scope_targets")
    op.drop_index(op.f("ix_admin_org_scope_targets_policy_id"), table_name="admin_org_scope_targets")
    op.drop_index(op.f("ix_admin_org_scope_targets_is_deleted"), table_name="admin_org_scope_targets")
    op.drop_index(op.f("ix_admin_org_scope_targets_id"), table_name="admin_org_scope_targets")
    op.drop_table("admin_org_scope_targets")

    op.drop_index(op.f("ix_admin_org_scope_policies_scope_mode"), table_name="admin_org_scope_policies")
    op.drop_index(op.f("ix_admin_org_scope_policies_recycle_stage"), table_name="admin_org_scope_policies")
    op.drop_index(op.f("ix_admin_org_scope_policies_org_node_id"), table_name="admin_org_scope_policies")
    op.drop_index(op.f("ix_admin_org_scope_policies_is_deleted"), table_name="admin_org_scope_policies")
    op.drop_index(op.f("ix_admin_org_scope_policies_id"), table_name="admin_org_scope_policies")
    op.drop_table("admin_org_scope_policies")

    op.drop_index(op.f("ix_admin_org_nodes_type"), table_name="admin_org_nodes")
    op.drop_index(op.f("ix_admin_org_nodes_recycle_stage"), table_name="admin_org_nodes")
    op.drop_index(op.f("ix_admin_org_nodes_path"), table_name="admin_org_nodes")
    op.drop_index(op.f("ix_admin_org_nodes_parent_id"), table_name="admin_org_nodes")
    op.drop_index(op.f("ix_admin_org_nodes_leader_id"), table_name="admin_org_nodes")
    op.drop_index(op.f("ix_admin_org_nodes_is_deleted"), table_name="admin_org_nodes")
    op.drop_index(op.f("ix_admin_org_nodes_id"), table_name="admin_org_nodes")
    op.drop_index(op.f("ix_admin_org_nodes_code"), table_name="admin_org_nodes")
    op.drop_table("admin_org_nodes")
