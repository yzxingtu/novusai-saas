"""
插件市场 Schema

定义市场 API 的请求和响应数据结构
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from app.core.base_schema import BaseSchema


class InstallStatus(str, Enum):
    """插件安装状态"""

    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    UPDATE_AVAILABLE = "update_available"


# ========================================
# Registry 数据结构（从 registry.json 解析）
# ========================================

class RegistryCategory(BaseSchema):
    """插件分类定义（来自 registry categories）"""

    code: str = Field(..., description="分类编码")
    name: str = Field(..., description="分类名称（i18n key 或显示文本）")
    icon: str = Field("lucide:puzzle", description="图标（lucide 图标名）")
    sort_order: int = Field(0, description="排序权重")


class RegistryPluginRepo(BaseSchema):
    """插件仓库地址（双节点）"""

    github: str | None = Field(None, description="GitHub 仓库全名（如 owner/repo）")
    gitee: str | None = Field(None, description="Gitee 仓库全名（如 owner/repo）")


# ========================================
# Marketplace API 响应
# ========================================

class MarketplacePluginResponse(BaseSchema):
    """市场插件信息"""

    # 基础信息
    name: str = Field(..., description="插件唯一标识")
    slug: str = Field(..., description="市场 slug（URL 友好）")
    display_name: str = Field(..., description="显示名称")
    version: str = Field(..., description="最新版本号")
    description: str | None = Field(None, description="插件描述")
    author: str | None = Field(None, description="作者")

    # 分类与标签
    plugin_type: str = Field(..., description="插件类型（adapter/skill/hook/api/storage/composite）")
    category: str | None = Field(None, description="插件分类（ai_model/storage/notification 等）")
    tags: list[str] | None = Field(None, description="标签列表")

    # 仓库信息
    repo: RegistryPluginRepo = Field(..., description="仓库地址（GitHub + Gitee 双节点）")
    official: bool = Field(False, description="是否官方插件")

    # 展示信息
    icon: str | None = Field(None, description="插件图标（lucide 图标名或 URL）")
    screenshots: list[str] | None = Field(None, description="截图 URL 列表")
    readme: str | None = Field(None, description="README 内容（Markdown，仅详情接口返回）")

    # 版本与兼容性
    min_platform_version: str | None = Field(None, description="最低平台版本要求")
    license: str | None = Field(None, description="开源许可证")
    changelog_url: str | None = Field(None, description="变更日志 URL")

    # 安全
    checksum_sha256: str | None = Field(None, description="插件包 SHA256 校验和")
    file_size_bytes: int | None = Field(None, description="插件包文件大小（字节）")

    # 安装状态（后端比对后填充）
    install_status: InstallStatus = Field(
        InstallStatus.NOT_INSTALLED,
        description="安装状态（not_installed/installed/update_available）",
    )
    installed_version: str | None = Field(
        None, description="本地已安装版本（未安装时为 None）",
    )
    local_plugin_id: int | None = Field(
        None, description="本地 Plugin 记录 ID（未安装时为 None）",
    )


class MarketplaceListResponse(BaseSchema):
    """市场插件列表响应"""

    items: list[MarketplacePluginResponse] = Field(
        default_factory=list, description="插件列表",
    )
    total: int = Field(0, description="总数")
    categories: list[RegistryCategory] = Field(
        default_factory=list, description="可用分类列表（前端渲染 Tab 用）",
    )
    mirror: str = Field("github", description="当前使用的镜像节点（github/gitee）")


class MarketplaceDetailResponse(MarketplacePluginResponse):
    """市场插件详情响应（含 README）"""

    readme: str | None = Field(None, description="README 内容（Markdown）")
    repo_url: str | None = Field(None, description="当前镜像的仓库主页 URL")


# ========================================
# Marketplace API 请求
# ========================================

class MarketplaceInstallRequest(BaseSchema):
    """市场安装请求"""

    version: str | None = Field(
        None, description="指定安装版本（默认安装最新版）",
    )


# ========================================
# 更新检查响应
# ========================================

class PluginUpdateInfo(BaseSchema):
    """单个插件的更新信息"""

    name: str = Field(..., description="插件唯一标识")
    slug: str = Field(..., description="市场 slug")
    display_name: str = Field(..., description="显示名称")
    current_version: str = Field(..., description="当前已安装版本")
    latest_version: str = Field(..., description="市场最新版本")
    changelog_url: str | None = Field(None, description="变更日志 URL")
    local_plugin_id: int = Field(..., description="本地 Plugin 记录 ID")


class UpdateCheckResponse(BaseSchema):
    """更新检查响应"""

    updates: list[PluginUpdateInfo] = Field(
        default_factory=list, description="有可用更新的插件列表",
    )
    total: int = Field(0, description="有更新的插件数量")


# ========================================
# 刷新缓存响应
# ========================================

class RegistryRefreshResponse(BaseSchema):
    """刷新缓存响应"""

    refreshed: bool = Field(True, description="是否刷新成功")
    plugin_count: int = Field(0, description="注册中心插件总数")
    mirror: str = Field("github", description="当前镜像节点")
    updated_at: str | None = Field(None, description="注册中心最后更新时间（ISO8601）")


__all__ = [
    "InstallStatus",
    "MarketplaceDetailResponse",
    "MarketplaceInstallRequest",
    "MarketplaceListResponse",
    "MarketplacePluginResponse",
    "PluginUpdateInfo",
    "RegistryCategory",
    "RegistryPluginRepo",
    "RegistryRefreshResponse",
    "UpdateCheckResponse",
]
