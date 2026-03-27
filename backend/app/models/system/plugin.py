"""
插件模型 / Plugin Model
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.core.deletion import DeletionDep, DeletionStrategy


class Plugin(BaseModel):
    """
    插件主表 / Plugin main table.
    """

    __tablename__ = "plugins"

    __delete_deps__ = [
        DeletionDep("PluginVersion", "plugin_id", DeletionStrategy.CASCADE_DELETE,
                    label_field="version", i18n_key="plugin_version"),
        DeletionDep("PluginLicense", "plugin_id", DeletionStrategy.CASCADE_DELETE,
                    label_field="id", i18n_key="plugin_license"),
    ]

    __table_args__ = (
        Index(
            "ix_plugins_name",
            "name",
            unique=True,
            postgresql_where="is_deleted = false",
        ),
        Index("ix_plugins_status", "status"),
        Index("ix_plugins_scope", "scope"),
    )

    __filterable__ = {
        "id": "id", "name": "name", "display_name": "display_name",
        "status": "status", "scope": "scope", "tier": "tier",
        "install_source": "install_source", "pricing_type": "pricing_type",
        "created_at": "created_at", "updated_at": "updated_at",
    }
    __sortable__ = {
        "id", "name", "display_name", "status",
        "created_at", "updated_at", "enabled_at",
    }
    __selectable__ = {
        "label": "display_name",
        "value": "id",
        "search": ["name", "display_name"],
        "extra": ["status", "scope", "icon"],
    }

    # ── 基本信息 ── / Basic info
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="插件唯一标识",
    )
    display_name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="显示名称",
    )
    version: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="当前版本",
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="描述",
    )
    author: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="作者",
    )

    # ── 外观 ── / Appearance
    icon: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="图标(Iconify字符串或图片URL)",
    )
    icon_color: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="图标颜色",
    )

    # ── 来源 ── / Source
    homepage: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="主页URL",
    )
    repository_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="仓库URL",
    )
    license_text: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="许可证",
    )
    tags: Mapped[list | None] = mapped_column(
        JSON, nullable=True, default=list, comment="标签",
    )

    # ── 分类与状态 ── / Category and status
    scope: Mapped[str] = mapped_column(
        String(40), nullable=False, comment="作用域",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="installed", comment="状态",
    )
    tier: Mapped[str] = mapped_column(
        String(20), nullable=False, default="community", comment="信任等级",
    )
    install_source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="local", comment="安装来源",
    )
    marketplace_slug: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="市场标识",
    )

    # ── 配置 ── / Config
    manifest: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, comment="清单内容",
    )
    config: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, comment="全局配置",
    )
    ai_requirements: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="AI需求",
    )

    # ── 定价 ── / Pricing
    pricing_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="free", comment="定价类型",
    )
    pricing_info: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="定价详情",
    )

    # ── 健康监控 ── / Health
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="最近错误",
    )
    error_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="连续错误次数",
    )

    # ── 依赖追踪 ── / Dependencies
    installed_packages: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, comment="已安装的Python依赖",
    )

    # ── 能力授权 ── / Capabilities
    granted_capabilities: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, comment="管理员授权的能力列表",
    )

    # ── 时间 ── / Timestamps
    installed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="安装时间",
    )
    enabled_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="启用时间",
    )

    # ── 关系 ── / Relationships
    versions = relationship(
        "PluginVersion", back_populates="plugin", lazy="noload",
    )
    licenses = relationship(
        "PluginLicense", back_populates="plugin", lazy="noload",
    )
