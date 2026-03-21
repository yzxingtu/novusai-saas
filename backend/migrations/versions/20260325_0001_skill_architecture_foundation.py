"""Skill architecture foundation tables and columns

Revision ID: 20260325_skill_arch_foundation
Revises: 20260324_drop_skill_pkg_aud
Create Date: 2026-03-25

Adds the first slice of the new Skill/Capability architecture:
- direct Skill metadata columns aligned with AgentScope-style SKILL.md
- skill_resources
- capabilities
- skill_capability_bindings
- agent_skill_grants
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260325_skill_arch_foundation"
down_revision: str | Sequence[str] | None = "20260324_drop_skill_pkg_aud"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("skills", sa.Column("key", sa.String(length=100), nullable=True))
    op.add_column(
        "skills",
        sa.Column(
            "source_type",
            sa.String(length=30),
            nullable=False,
            server_default="custom",
        ),
    )
    op.add_column("skills", sa.Column("source_ref", sa.String(length=255), nullable=True))
    op.add_column("skills", sa.Column("skill_md", sa.Text(), nullable=True))
    op.add_column(
        "skills",
        sa.Column(
            "version",
            sa.String(length=50),
            nullable=False,
            server_default="1.0.0",
        ),
    )
    op.add_column(
        "skills",
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
    )
    op.add_column(
        "skills",
        sa.Column(
            "is_readonly",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index("ix_skills_key", "skills", ["key"], unique=True)
    op.create_index("ix_skills_source_status", "skills", ["source_type", "status"])

    op.create_table(
        "skill_resources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("resource_type", sa.String(length=20), nullable=False, server_default="other"),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("skill_id", "path", name="uq_skill_resource_path"),
    )
    op.create_index("ix_skill_resources_skill_id", "skill_resources", ["skill_id"])
    op.create_index("ix_skill_resources_resource_type", "skill_resources", ["resource_type"])
    op.create_index(
        "ix_skill_resources_skill_type",
        "skill_resources",
        ["skill_id", "resource_type"],
    )
    op.create_index("ix_skill_resources_is_deleted", "skill_resources", ["is_deleted"])

    op.create_table(
        "capabilities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True),
        sa.Column("owner_tenant_id", sa.Integer(), nullable=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("executor_type", sa.String(length=30), nullable=False, server_default="builtin"),
        sa.Column("executor_ref", sa.String(length=255), nullable=True),
        sa.Column("input_schema", sa.JSON(), nullable=True),
        sa.Column("output_schema", sa.JSON(), nullable=True),
        sa.Column("default_consent_mode", sa.String(length=20), nullable=False, server_default="auto"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("security_policy", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_capabilities_owner_tenant_id", "capabilities", ["owner_tenant_id"])
    op.create_index("ix_capabilities_key", "capabilities", ["key"], unique=True)
    op.create_index("ix_capabilities_executor_type", "capabilities", ["executor_type"])
    op.create_index("ix_capabilities_status", "capabilities", ["status"])
    op.create_index(
        "ix_capabilities_owner_status",
        "capabilities",
        ["owner_tenant_id", "status"],
    )
    op.create_index("ix_capabilities_is_deleted", "capabilities", ["is_deleted"])

    op.create_table(
        "skill_capability_bindings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("capability_id", sa.Integer(), nullable=False),
        sa.Column("activation_mode", sa.String(length=20), nullable=False, server_default="on_demand"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["capability_id"], ["capabilities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("skill_id", "capability_id", name="uq_skill_capability_binding"),
    )
    op.create_index("ix_skill_capability_bindings_skill_id", "skill_capability_bindings", ["skill_id"])
    op.create_index("ix_skill_capability_bindings_capability_id", "skill_capability_bindings", ["capability_id"])
    op.create_index(
        "ix_skill_capability_binding_sort",
        "skill_capability_bindings",
        ["skill_id", "sort_order"],
    )
    op.create_index(
        "ix_skill_capability_bindings_is_deleted",
        "skill_capability_bindings",
        ["is_deleted"],
    )

    op.create_table(
        "agent_skill_grants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("config_override", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("default_consent_mode", sa.String(length=20), nullable=False, server_default="auto"),
        sa.Column("capability_consent_overrides", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "skill_id", name="uq_agent_skill_grant"),
    )
    op.create_index("ix_agent_skill_grants_tenant_id", "agent_skill_grants", ["tenant_id"])
    op.create_index("ix_agent_skill_grants_agent_id", "agent_skill_grants", ["agent_id"])
    op.create_index("ix_agent_skill_grants_skill_id", "agent_skill_grants", ["skill_id"])
    op.create_index(
        "ix_agent_skill_grant_agent_enabled",
        "agent_skill_grants",
        ["agent_id", "enabled"],
    )
    op.create_index("ix_agent_skill_grants_is_deleted", "agent_skill_grants", ["is_deleted"])

    op.drop_table("agent_skill_bindings")


def downgrade() -> None:
    op.create_table(
        "agent_skill_bindings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("package_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("config_override", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consent_mode", sa.String(length=20), nullable=False, server_default="auto"),
        sa.Column("skill_consent_overrides", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["package_id"], ["skill_packages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "package_id", name="uq_agent_skill_package_binding"),
    )
    op.create_index("ix_agent_skill_bindings_tenant_id", "agent_skill_bindings", ["tenant_id"])
    op.create_index("ix_agent_skill_bindings_agent_id", "agent_skill_bindings", ["agent_id"])
    op.create_index("ix_agent_skill_bindings_package_id", "agent_skill_bindings", ["package_id"])
    op.create_index(
        "ix_agent_skill_bindings_agent_enabled",
        "agent_skill_bindings",
        ["agent_id", "enabled"],
    )
    op.create_index("ix_agent_skill_bindings_is_deleted", "agent_skill_bindings", ["is_deleted"])

    op.drop_table("agent_skill_grants")
    op.drop_table("skill_capability_bindings")
    op.drop_table("capabilities")
    op.drop_table("skill_resources")
    op.drop_index("ix_skills_source_status", table_name="skills")
    op.drop_index("ix_skills_key", table_name="skills")
    op.drop_column("skills", "is_readonly")
    op.drop_column("skills", "status")
    op.drop_column("skills", "version")
    op.drop_column("skills", "skill_md")
    op.drop_column("skills", "source_ref")
    op.drop_column("skills", "source_type")
    op.drop_column("skills", "key")
