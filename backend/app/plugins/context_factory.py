"""
插件上下文工厂

根据 manifest.api_version 创建对应版本的 PluginContext。
当前仅支持 V1，预留版本化扩展机制。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.plugins.context import PluginContext
from app.plugins.exceptions import PluginError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.plugins.manifest import PluginManifest

# PluginContext 即 V1，不重命名以保持向后兼容
PluginContextV1 = PluginContext

# 版本 → Context 类映射
_VERSION_MAP: dict[str, type] = {
    "1": PluginContextV1,
}


def create_plugin_context(
    plugin_name: str,
    manifest: PluginManifest,
    db: AsyncSession,
    granted_capabilities: list[str] | None = None,
) -> PluginContext:
    """
    根据 manifest.api_version 创建对应版本的 PluginContext。

    Args:
        plugin_name: 插件名
        manifest: 插件清单
        db: 数据库会话
        granted_capabilities: 授权能力列表

    Returns:
        PluginContext 实例

    Raises:
        PluginError: 不支持的 API 版本
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
    )
