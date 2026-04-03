"""
插件许可证模型 / Plugin License Model
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel


class PluginLicense(BaseModel):
    """
    插件许可证表 / Plugin license table.
    """

    __tablename__ = "plugin_licenses"

    __filterable__ = {
        "id": "id",
        "plugin_id": "plugin_id",
        "license_type": "license_type",
        "is_valid": "is_valid",
    }
    __sortable__ = {"id", "activated_at", "created_at"}

    plugin_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("plugins.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="插件ID",
    )
    license_key: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="License Key",
    )
    license_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="trial",
        comment="许可类型 (trial/fixed_term/perpetual)",
    )
    version_scope: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="版本范围",
    )
    buyer_email: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="购买者邮箱",
    )
    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="签发时间",
    )
    trial_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="试用到期时间",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="正式 License 到期时间（仅 fixed_term 使用，None 表示永久）",
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="激活时间",
    )
    is_valid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否有效",
    )

    plugin = relationship("Plugin", back_populates="licenses", lazy="noload")
