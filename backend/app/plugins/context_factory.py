"""
Plugin context factory / 插件上下文工厂

Creates the corresponding version of PluginContext based on manifest.api_version.
Currently only V1 is supported; versioned extension mechanism is reserved.
/
根据 manifest.api_version 创建对应版本的 PluginContext。
当前仅支持 V1，预留版本化扩展机制。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.plugins.context import PluginContext, RequestContext
from app.plugins.exceptions import PluginError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.plugins.manifest import PluginManifest

# PluginContext is V1, not renamed to maintain backward compatibility
# / PluginContext 即 V1，不重命名以保持向后兼容
PluginContextV1 = PluginContext

# Version → Context class mapping / 版本 → Context 类映射
_VERSION_MAP: dict[str, type] = {
    "1": PluginContextV1,
}


def create_plugin_context(
    plugin_name: str,
    manifest: PluginManifest,
    db: AsyncSession,
    granted_capabilities: list[str] | None = None,
    request_context: RequestContext | None = None,
) -> PluginContext:
    """
    Create the corresponding version of PluginContext based on manifest.api_version.
    / 根据 manifest.api_version 创建对应版本的 PluginContext。

    Args:
        plugin_name: Plugin name / 插件名
        manifest: Plugin manifest / 插件清单
        db: Database session / 数据库会话
        granted_capabilities: Granted capabilities list / 授权能力列表
        request_context: Request context (tenant_id/user_id/user_role/permissions/request_id)
                         / 请求上下文

    Returns:
        PluginContext instance / PluginContext 实例

    Raises:
        PluginError: Unsupported API version / 不支持的 API 版本
    """
    version = getattr(manifest, "api_version", "1") or "1"
    ctx_class = _VERSION_MAP.get(version)

    if ctx_class is None:
        raise PluginError(
            message=f"Unsupported plugin API version: {version}. "
            f"Supported versions: {sorted(_VERSION_MAP.keys())}",
        )

    return ctx_class(
        plugin_name=plugin_name,
        manifest=manifest,
        db=db,
        granted_capabilities=granted_capabilities,
        request_context=request_context,
    )
