"""
插件数据库迁移记录模型

记录每个插件已执行的数据库迁移，支持按序执行和回滚。
"""

from datetime import datetime

from sqlalchemy import Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel, utc_now


class PluginMigration(BaseModel):
    """
    插件迁移记录

    每个插件可包含 migrations/ 目录，其中的 SQL 文件按序号执行。
    本表记录已执行的迁移，用于防止重复执行和支持回滚。
    """

    __tablename__ = "plugin_migrations"

    __table_args__ = (
        UniqueConstraint(
            "plugin_name", "version",
            name="uq_plugin_migrations_name_version",
        ),
        Index("ix_plugin_migrations_plugin_name", "plugin_name"),
    )

    plugin_name: Mapped[str] = mapped_column(
        comment="插件名称",
    )
    version: Mapped[str] = mapped_column(
        comment="迁移版本号（如 001, 002）",
    )
    filename: Mapped[str] = mapped_column(
        comment="迁移文件名（如 001_create_tables.sql）",
    )
    checksum: Mapped[str] = mapped_column(
        comment="迁移文件 SHA256 校验和",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        default=None,
        comment="迁移描述（从文件名或注释中提取）",
    )
    applied_at: Mapped[datetime] = mapped_column(
        default=lambda: utc_now(),
        comment="迁移执行时间",
    )
