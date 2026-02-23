"""
插件版本模型
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel


class PluginVersion(BaseModel):
    """
    插件版本历史表
    """

    __tablename__ = "plugin_versions"

    __filterable__ = {"id": "id", "plugin_id": "plugin_id", "version": "version", "status": "status"}
    __sortable__ = {"id", "version", "installed_at", "created_at"}

    plugin_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("plugins.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="插件ID",
    )
    version: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="版本号",
    )
    manifest: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, comment="该版本清单",
    )
    changelog: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="变更日志",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", comment="版本状态",
    )
    installed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="安装时间",
    )
    rolled_back_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="回退时间",
    )

    plugin = relationship("Plugin", back_populates="versions", lazy="noload")
