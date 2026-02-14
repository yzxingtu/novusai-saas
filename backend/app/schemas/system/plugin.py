"""
插件相关 Schema

定义插件管理 API 的请求和响应数据结构
"""

from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.base_schema import BaseSchema


class PluginResponse(BaseSchema):
    """插件响应"""

    id: int = Field(..., description="ID")
    name: str = Field(..., description="插件唯一标识")
    display_name: str = Field(..., description="显示名称")
    version: str = Field(..., description="版本号")
    description: str | None = Field(None, description="描述")
    author: str | None = Field(None, description="作者")
    plugin_type: str = Field(..., description="插件类型")
    status: str = Field(..., description="状态")
    entry_point: str = Field(..., description="入口点")
    manifest: dict[str, Any] | None = Field(None, description="manifest")
    is_system: bool = Field(False, description="是否系统内置")
    required_permissions: list[str] | None = Field(None, description="所需权限")
    dependencies: dict[str, str] | None = Field(None, description="依赖声明")
    conflicts: list[str] | None = Field(None, description="互斥插件")
    platform_version: str | None = Field(None, description="最低平台版本")
    config_schema: dict[str, Any] | None = Field(None, description="配置 Schema")
    default_config: dict[str, Any] | None = Field(None, description="默认配置")
    version_history: list[dict[str, Any]] | None = Field(None, description="版本历史")
    icon: str | None = Field(None, description="图标")
    homepage: str | None = Field(None, description="主页")
    readme: str | None = Field(None, description="README")
    downloads_count: int = Field(0, description="下载次数")
    rating: float | None = Field(None, description="评分")
    tags: list[str] | None = Field(None, description="标签")
    category: str | None = Field(None, description="分类")
    screenshots: list[str] | None = Field(None, description="截图")
    source_url: str | None = Field(None, description="源码地址")
    license: str | None = Field(None, description="许可证")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class PluginCreateRequest(BaseSchema):
    """创建插件请求"""

    name: str = Field(..., min_length=1, max_length=255, description="插件唯一标识")
    display_name: str = Field(..., min_length=1, max_length=255, description="显示名称")
    version: str = Field("0.0.1", description="版本号")
    description: str | None = Field(None, description="描述")
    author: str | None = Field(None, max_length=255, description="作者")
    plugin_type: str = Field("composite", description="插件类型")
    entry_point: str = Field(..., min_length=1, description="入口点")
    manifest: dict[str, Any] | None = Field(None, description="manifest")
    is_system: bool = Field(False, description="是否系统内置")
    required_permissions: list[str] | None = Field(None, description="所需权限")
    dependencies: dict[str, str] | None = Field(None, description="依赖声明")
    conflicts: list[str] | None = Field(None, description="互斥插件")
    platform_version: str | None = Field(None, description="最低平台版本")
    config_schema: dict[str, Any] | None = Field(None, description="配置 Schema")
    default_config: dict[str, Any] | None = Field(None, description="默认配置")
    icon: str | None = Field(None, description="图标")
    homepage: str | None = Field(None, description="主页")
    readme: str | None = Field(None, description="README")


class PluginUpdateRequest(BaseSchema):
    """更新插件请求"""

    display_name: str | None = Field(None, min_length=1, max_length=255, description="显示名称")
    version: str | None = Field(None, description="版本号")
    description: str | None = Field(None, description="描述")
    author: str | None = Field(None, description="作者")
    plugin_type: str | None = Field(None, description="插件类型")
    entry_point: str | None = Field(None, description="入口点")
    manifest: dict[str, Any] | None = Field(None, description="manifest")
    required_permissions: list[str] | None = Field(None, description="所需权限")
    dependencies: dict[str, str] | None = Field(None, description="依赖声明")
    conflicts: list[str] | None = Field(None, description="互斥插件")
    platform_version: str | None = Field(None, description="最低平台版本")
    config_schema: dict[str, Any] | None = Field(None, description="配置 Schema")
    default_config: dict[str, Any] | None = Field(None, description="默认配置")
    icon: str | None = Field(None, description="图标")
    homepage: str | None = Field(None, description="主页")
    readme: str | None = Field(None, description="README")
    tags: list[str] | None = Field(None, description="标签")
    category: str | None = Field(None, description="分类")
    screenshots: list[str] | None = Field(None, description="截图")
    source_url: str | None = Field(None, description="源码地址")
    license: str | None = Field(None, description="许可证")


class PluginInstallRequest(BaseSchema):
    """安装插件请求（通过 entry_point）"""

    entry_point: str = Field(..., min_length=1, description="入口点路径")
    is_system: bool = Field(False, description="是否标记为系统内置")


class PluginToggleRequest(BaseSchema):
    """启用/禁用插件请求"""

    is_active: bool = Field(..., description="是否启用")


class TenantPluginResponse(BaseSchema):
    """租户插件响应"""

    id: int = Field(..., description="ID")
    tenant_id: int = Field(..., description="租户 ID")
    plugin_id: int = Field(..., description="插件 ID")
    is_active: bool = Field(False, description="是否启用")
    config: dict[str, Any] | None = Field(None, description="自定义配置")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class TenantPluginEnableRequest(BaseSchema):
    """租户启用插件请求"""

    plugin_id: int = Field(..., description="插件 ID")
    config: dict[str, Any] | None = Field(None, description="自定义配置")


class TenantPluginConfigRequest(BaseSchema):
    """租户更新插件配置请求"""

    config: dict[str, Any] = Field(..., description="自定义配置")


__all__ = [
    "PluginResponse",
    "PluginCreateRequest",
    "PluginInstallRequest",
    "PluginUpdateRequest",
    "PluginToggleRequest",
    "TenantPluginResponse",
    "TenantPluginEnableRequest",
    "TenantPluginConfigRequest",
]
