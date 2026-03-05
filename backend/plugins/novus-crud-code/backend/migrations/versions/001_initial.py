"""DataForge Studio plugin initial tables

Revision ID: ncc_001
Revises:
Create Date: 2026-03-01

Creates:
- ncc_projects        — 项目（一个项目可包含多张表）
- ncc_table_schemas   — 表结构定义（schema_config JSONB 存字段列表）
- ncc_table_relations — 表关联关系（from_table → to_table FK）
- ncc_records         — 动态数据行（data JSONB 存任意字段值）
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "ncc_001"
down_revision = None
branch_labels = ("plugin_novus_crud_code",)
depends_on = None


def upgrade() -> None:
    # ── ncc_projects ──
    op.create_table(
        "ncc_projects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("icon", sa.String(100), nullable=True, server_default="lucide:database"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false", index=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_ncc_project_name", "ncc_projects", ["name"])
    op.create_index("ix_ncc_projects_name", "ncc_projects", ["name"])

    # ── ncc_table_schemas ──
    op.create_table(
        "ncc_table_schemas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("ncc_projects.id", ondelete="CASCADE", name="fk_ncc_ts_project"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("schema_config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("form_config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("ui_config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false", index=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_ncc_schema_project_name",
        "ncc_table_schemas",
        ["project_id", "name"],
    )
    op.create_index(
        "ix_ncc_schemas_project_sort",
        "ncc_table_schemas",
        ["project_id", "sort_order"],
    )

    # ── ncc_table_relations ──
    op.create_table(
        "ncc_table_relations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("ncc_projects.id", ondelete="CASCADE", name="fk_ncc_rel_project"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "from_schema_id",
            sa.Integer(),
            sa.ForeignKey("ncc_table_schemas.id", ondelete="CASCADE", name="fk_ncc_rel_from"),
            nullable=False,
        ),
        sa.Column(
            "to_schema_id",
            sa.Integer(),
            sa.ForeignKey("ncc_table_schemas.id", ondelete="CASCADE", name="fk_ncc_rel_to"),
            nullable=False,
        ),
        sa.Column("from_field", sa.String(200), nullable=False),
        sa.Column("to_field", sa.String(200), nullable=False),
        sa.Column("relation_type", sa.String(20), nullable=False, server_default="one_to_many"),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false", index=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_ncc_relations_from",
        "ncc_table_relations",
        ["from_schema_id"],
    )
    op.create_index(
        "ix_ncc_relations_to",
        "ncc_table_relations",
        ["to_schema_id"],
    )

    # ── ncc_records ──
    op.create_table(
        "ncc_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "schema_id",
            sa.Integer(),
            sa.ForeignKey("ncc_table_schemas.id", ondelete="CASCADE", name="fk_ncc_rec_schema"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("ncc_projects.id", ondelete="CASCADE", name="fk_ncc_rec_project"),
            nullable=False,
            index=True,
        ),
        sa.Column("data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false", index=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_ncc_records_schema_created",
        "ncc_records",
        ["schema_id", "created_at"],
    )
    op.create_index(
        "ix_ncc_records_schema_sort",
        "ncc_records",
        ["schema_id", "sort_order"],
    )
    op.execute(
        "CREATE INDEX ix_ncc_records_data_gin ON ncc_records USING gin(data jsonb_path_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ncc_records_data_gin")
    op.drop_table("ncc_records")
    op.drop_table("ncc_table_relations")
    op.drop_table("ncc_table_schemas")
    op.drop_table("ncc_projects")
