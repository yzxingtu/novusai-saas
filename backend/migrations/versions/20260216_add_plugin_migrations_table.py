"""
Add plugin_migrations table

Track database migrations applied by plugins.

Revision ID: 20260216_plm
Revises: 20260216_awm
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa

revision = "20260216_plm"
down_revision = "20260216_awm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plugin_migrations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("plugin_name", sa.String(length=100), nullable=False, comment="插件名称"),
        sa.Column("version", sa.String(length=50), nullable=False, comment="迁移版本号"),
        sa.Column("filename", sa.String(length=255), nullable=False, comment="迁移文件名"),
        sa.Column("checksum", sa.String(length=64), nullable=False, comment="SHA256 校验和"),
        sa.Column("description", sa.Text(), nullable=True, comment="迁移描述"),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="迁移执行时间",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "plugin_name", "version", name="uq_plugin_migrations_name_version"
        ),
    )
    op.create_index(
        "ix_plugin_migrations_plugin_name",
        "plugin_migrations",
        ["plugin_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_plugin_migrations_plugin_name", table_name="plugin_migrations")
    op.drop_table("plugin_migrations")
