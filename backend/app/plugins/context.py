"""
插件运行时上下文

封装插件在运行时所需的所有依赖和环境信息
"""

from __future__ import annotations

from dataclasses import dataclass, field
from logging import Logger
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.ai.events.bus import EventBus
    from app.ai.tools.registry import ToolRegistry


@dataclass
class PluginContext:
    """
    插件运行时上下文

    在插件生命周期方法和扩展点中传递，提供：
    - config: 插件实例配置（合并 default_config + 租户自定义 config）
    - tenant_id: 当前租户 ID（平台级操作时为 None）
    - db: 异步数据库会话
    - logger: 插件专属 logger
    - event_bus: 事件总线实例
    - tool_registry: 工具注册表实例
    - plugin_name: 插件标识名称
    - plugin_version: 插件版本号

    使用示例::

        async def on_enable(self, ctx: PluginContext) -> None:
            ctx.logger.info("Plugin enabled for tenant %s", ctx.tenant_id)
            config = ctx.config
            bus = ctx.event_bus
    """

    config: dict[str, Any] = field(default_factory=dict)
    tenant_id: int | None = None
    db: AsyncSession | None = None
    logger: Logger | None = None
    event_bus: EventBus | None = None
    tool_registry: ToolRegistry | None = None
    plugin_name: str = ""
    plugin_version: str = ""
    plugin_scope: str = "all_tenants"
    skill_config: dict[str, Any] = field(default_factory=dict)
    model_id: int | None = None

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        安全获取配置项

        Args:
            key: 配置键
            default: 默认值

        Returns:
            配置值
        """
        return self.config.get(key, default)


__all__ = ["PluginContext"]
