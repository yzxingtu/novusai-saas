"""
插件模型

平台级插件注册表，管理插件元数据、配置和生命周期
"""

from sqlalchemy import Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel
from app.enums.plugin import PluginScopeEnum, PluginStatusEnum, PluginTypeEnum


class Plugin(BaseModel):
    """
    插件模型

    平台级插件注册表，记录插件元数据、配置 Schema、状态等信息。
    一个 Plugin 可被多个 Tenant 启用（通过 TenantPlugin 关联）。
    """

    __tablename__ = "plugins"

    __filterable__ = {
        "id": "id",
        "name": "name",
        "display_name": "display_name",
        "plugin_type": "plugin_type",
        "status": "status",
        "scope": "scope",
        "is_system": "is_system",
        "author": "author",
        "category": "category",
        "install_source": "install_source",
        "created_at": "created_at",
    }

    __sortable__ = [
        "created_at", "updated_at", "name", "display_name",
        "downloads_count", "rating",
    ]

    __table_args__ = (
        UniqueConstraint("name", name="uq_plugins_name"),
        Index("ix_plugins_type_status", "plugin_type", "status"),
    )

    name: Mapped[str] = mapped_column(
        comment="插件唯一标识（如 novusai-anthropic-adapter）",
    )
    display_name: Mapped[str] = mapped_column(
        comment="插件显示名称",
    )
    version: Mapped[str] = mapped_column(
        default="0.0.1",
        comment="当前版本号（semver）",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        default=None,
        comment="插件描述",
    )
    author: Mapped[str | None] = mapped_column(
        default=None,
        comment="作者",
    )
    plugin_type: Mapped[str] = mapped_column(
        default=PluginTypeEnum.COMPOSITE.value,
        comment="插件类型（adapter/tool/hook/api/skill/composite）",
    )
    status: Mapped[str] = mapped_column(
        default=PluginStatusEnum.INSTALLED.value,
        comment="插件状态（installed/enabled/disabled/error）",
    )
    scope: Mapped[str] = mapped_column(
        default=PluginScopeEnum.ALL_TENANTS.value,
        comment="作用域（platform_only/all_tenants/assigned_tenants/global）",
    )
    entry_point: Mapped[str] = mapped_column(
        comment="入口点（如 app.plugins.anthropic.main.AnthropicPlugin）",
    )
    manifest: Mapped[dict | None] = mapped_column(
        JSONB,
        default=None,
        comment="完整 manifest.json 内容",
    )
    is_system: Mapped[bool] = mapped_column(
        default=False,
        comment="是否为系统内置插件（不可卸载/禁用）",
    )
    required_permissions: Mapped[list | None] = mapped_column(
        JSONB,
        default=None,
        comment="所需权限声明列表（如 [\"db:read\", \"http:outbound\"]）",
    )
    dependencies: Mapped[dict | None] = mapped_column(
        JSONB,
        default=None,
        comment="依赖声明（如 {\"novusai-core\": \">=1.0.0\"}）",
    )
    conflicts: Mapped[list | None] = mapped_column(
        JSONB,
        default=None,
        comment="互斥插件列表（如 [\"old-adapter\"]）",
    )
    platform_version: Mapped[str | None] = mapped_column(
        default=None,
        comment="最低平台版本要求（如 >=2.0.0）",
    )
    config_schema: Mapped[dict | None] = mapped_column(
        JSONB,
        default=None,
        comment="配置项 JSON Schema（用于前端动态表单渲染）",
    )
    default_config: Mapped[dict | None] = mapped_column(
        JSONB,
        default=None,
        comment="默认配置值",
    )
    version_history: Mapped[list | None] = mapped_column(
        JSONB,
        default=None,
        comment="版本历史记录",
    )
    icon: Mapped[str | None] = mapped_column(
        default=None,
        comment="插件图标（URL 或 Lucide 图标名）",
    )
    homepage: Mapped[str | None] = mapped_column(
        default=None,
        comment="插件主页 URL",
    )
    readme: Mapped[str | None] = mapped_column(
        Text,
        default=None,
        comment="README 内容（Markdown）",
    )

    # ========================================
    # 插件市场预留字段
    # ========================================
    downloads_count: Mapped[int] = mapped_column(
        default=0,
        comment="下载/安装次数（插件市场统计）",
    )
    rating: Mapped[float | None] = mapped_column(
        default=None,
        comment="评分（1.0-5.0，插件市场）",
    )
    tags: Mapped[list | None] = mapped_column(
        JSONB,
        default=None,
        comment="分类标签（如 [\"ai\", \"adapter\", \"openai\"]）",
    )
    category: Mapped[str | None] = mapped_column(
        default=None,
        comment="插件分类（如 ai-model, productivity, analytics）",
    )
    screenshots: Mapped[list | None] = mapped_column(
        JSONB,
        default=None,
        comment="截图 URL 列表（插件市场展示）",
    )
    source_url: Mapped[str | None] = mapped_column(
        default=None,
        comment="插件源码仓库 URL（如 GitHub 地址）",
    )
    license: Mapped[str | None] = mapped_column(
        default=None,
        comment="开源许可证（如 MIT, Apache-2.0）",
    )
    install_source: Mapped[str | None] = mapped_column(
        default=None,
        comment="安装来源（local/marketplace/builtin/entry_point）",
    )
    marketplace_slug: Mapped[str | None] = mapped_column(
        default=None,
        comment="插件市场 slug（市场安装时填写，用于后续升级匹配）",
    )
