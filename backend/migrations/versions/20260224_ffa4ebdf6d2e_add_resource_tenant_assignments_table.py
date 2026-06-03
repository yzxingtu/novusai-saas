"""add_resource_tenant_assignments_table

Revision ID: ffa4ebdf6d2e
Revises: 20260225_0001
Create Date: 2026-02-24 20:57:03.978763+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ffa4ebdf6d2e'
down_revision: Union[str, None] = '20260225_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema.

    1. Create resource_tenant_assignments table
    2. Batch UPDATE old scope values across 7 tables
    """
    # ── 1. Create resource_tenant_assignments table ──
    op.create_table(
        "resource_tenant_assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False, index=True,
                  comment="资源类型（skill_package / agent / knowledge_base / plugin 等）"),
        sa.Column("resource_id", sa.Integer(), nullable=False,
                  comment="资源 ID"),
        sa.Column("tenant_id", sa.Integer(), nullable=False,
                  comment="被分配的企业 ID"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true"),
                  comment="是否启用"),
        sa.Column("config", sa.JSON(), nullable=True,
                  comment="企业级配置（可选）"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resource_type", "resource_id", "tenant_id",
                            name="uq_resource_tenant_assignment"),
    )
    op.create_index("ix_rta_type_resource", "resource_tenant_assignments",
                    ["resource_type", "resource_id"])
    op.create_index("ix_rta_tenant", "resource_tenant_assignments", ["tenant_id"])

    # ── 2. Batch UPDATE old scope values ──
    # agents: admin→admin_only, tenant→all_tenants, global→global_shared
    op.execute(sa.text("UPDATE agents SET scope = 'admin_only' WHERE scope = 'admin'"))
    op.execute(sa.text("UPDATE agents SET scope = 'all_tenants' WHERE scope = 'tenant'"))
    op.execute(sa.text("UPDATE agents SET scope = 'global_shared' WHERE scope = 'global'"))

    # skill_packages: same mapping
    op.execute(sa.text("UPDATE skill_packages SET scope = 'admin_only' WHERE scope = 'admin'"))
    op.execute(sa.text("UPDATE skill_packages SET scope = 'all_tenants' WHERE scope = 'tenant'"))
    op.execute(sa.text("UPDATE skill_packages SET scope = 'global_shared' WHERE scope = 'global'"))

    # knowledge_bases: same mapping
    op.execute(sa.text("UPDATE knowledge_bases SET scope = 'admin_only' WHERE scope = 'admin'"))
    op.execute(sa.text("UPDATE knowledge_bases SET scope = 'all_tenants' WHERE scope = 'tenant'"))
    op.execute(sa.text("UPDATE knowledge_bases SET scope = 'global_shared' WHERE scope = 'global'"))

    # permissions: admin→admin_only, tenant→all_tenants, both→global_shared
    # NOTE: RBAC permission sync at app startup already creates rows with new scope values.
    # Only UPDATE rows where the new-scope equivalent doesn't exist yet (avoid unique constraint).
    # Stale old-scope rows (disabled by sync) are left as-is — they have FK children and
    # will be cleaned up naturally when the sync re-parents them on next full sync.
    op.execute(sa.text("""
        UPDATE permissions p SET scope = 'admin_only'
        WHERE p.scope = 'admin'
        AND NOT EXISTS (
            SELECT 1 FROM permissions p2 WHERE p2.code = p.code AND p2.scope = 'admin_only'
        )
    """))
    op.execute(sa.text("""
        UPDATE permissions p SET scope = 'all_tenants'
        WHERE p.scope = 'tenant'
        AND NOT EXISTS (
            SELECT 1 FROM permissions p2 WHERE p2.code = p.code AND p2.scope = 'all_tenants'
        )
    """))
    op.execute(sa.text("""
        UPDATE permissions p SET scope = 'global_shared'
        WHERE p.scope = 'both'
        AND NOT EXISTS (
            SELECT 1 FROM permissions p2 WHERE p2.code = p.code AND p2.scope = 'global_shared'
        )
    """))

    # system_config_groups: platform→admin_only, tenant→all_tenants
    op.execute(sa.text("UPDATE system_config_groups SET scope = 'admin_only' WHERE scope = 'platform'"))
    op.execute(sa.text("UPDATE system_config_groups SET scope = 'all_tenants' WHERE scope = 'tenant'"))

    # system_configs: same mapping
    op.execute(sa.text("UPDATE system_configs SET scope = 'admin_only' WHERE scope = 'platform'"))
    op.execute(sa.text("UPDATE system_configs SET scope = 'all_tenants' WHERE scope = 'tenant'"))



def downgrade() -> None:
    """Downgrade database schema."""
    # ── Reverse scope value UPDATEs ──
    # system_configs
    op.execute(sa.text("UPDATE system_configs SET scope = 'platform' WHERE scope = 'admin_only'"))
    op.execute(sa.text("UPDATE system_configs SET scope = 'tenant' WHERE scope = 'all_tenants'"))

    # system_config_groups
    op.execute(sa.text("UPDATE system_config_groups SET scope = 'platform' WHERE scope = 'admin_only'"))
    op.execute(sa.text("UPDATE system_config_groups SET scope = 'tenant' WHERE scope = 'all_tenants'"))

    # permissions
    op.execute(sa.text("UPDATE permissions SET scope = 'admin' WHERE scope = 'admin_only'"))
    op.execute(sa.text("UPDATE permissions SET scope = 'tenant' WHERE scope = 'all_tenants'"))
    op.execute(sa.text("UPDATE permissions SET scope = 'both' WHERE scope = 'global_shared'"))

    # knowledge_bases
    op.execute(sa.text("UPDATE knowledge_bases SET scope = 'admin' WHERE scope = 'admin_only'"))
    op.execute(sa.text("UPDATE knowledge_bases SET scope = 'tenant' WHERE scope = 'all_tenants'"))
    op.execute(sa.text("UPDATE knowledge_bases SET scope = 'global' WHERE scope = 'global_shared'"))

    # skill_packages
    op.execute(sa.text("UPDATE skill_packages SET scope = 'admin' WHERE scope = 'admin_only'"))
    op.execute(sa.text("UPDATE skill_packages SET scope = 'tenant' WHERE scope = 'all_tenants'"))
    op.execute(sa.text("UPDATE skill_packages SET scope = 'global' WHERE scope = 'global_shared'"))

    # agents
    op.execute(sa.text("UPDATE agents SET scope = 'admin' WHERE scope = 'admin_only'"))
    op.execute(sa.text("UPDATE agents SET scope = 'tenant' WHERE scope = 'all_tenants'"))
    op.execute(sa.text("UPDATE agents SET scope = 'global' WHERE scope = 'global_shared'"))

    # ── Drop resource_tenant_assignments table ──
    op.drop_index("ix_rta_tenant", table_name="resource_tenant_assignments")
    op.drop_index("ix_rta_type_resource", table_name="resource_tenant_assignments")
    op.drop_table("resource_tenant_assignments")
