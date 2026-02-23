"""
插件抽象基类

所有插件必须继承 PluginBase，按需覆盖生命周期钩子。
所有钩子有默认空实现，插件开发者只需覆盖需要的方法。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.plugins.context import PluginContext


class PluginBase:
    """
    插件抽象基类

    生命周期钩子（全部可选，默认空实现）：
    - on_install:   安装后调用（首次安装）
    - on_enable:    启用时调用
    - on_disable:   禁用时调用
    - on_uninstall: 卸载前调用
    - on_upgrade:   版本升级后调用
    """

    async def on_install(self, ctx: PluginContext) -> None:
        """安装后钩子（首次安装时调用）"""

    async def on_enable(self, ctx: PluginContext) -> None:
        """启用钩子"""

    async def on_disable(self, ctx: PluginContext) -> None:
        """禁用钩子"""

    async def on_uninstall(self, ctx: PluginContext) -> None:
        """卸载前钩子"""

    async def on_upgrade(self, ctx: PluginContext, old_version: str) -> None:
        """版本升级后钩子"""
