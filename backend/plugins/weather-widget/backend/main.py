"""天气组件插件 / Plugin.

提供顶部导航天气组件 + AI 技能包，基于免 Key 的公开天气服务。"""

from app.plugins.base import PluginBase


class WeatherWidgetPlugin(PluginBase):
    """天气组件插件 / Weather widget plugin."""

    async def on_install(self, ctx) -> None:
        ctx.get_logger().info("Weather widget plugin installed")

    async def on_enable(self, ctx) -> None:
        ctx.get_logger().info("Weather widget plugin enabled")

    async def on_disable(self, ctx) -> None:
        ctx.get_logger().info("Weather widget plugin disabled")

    async def on_uninstall(self, ctx) -> None:
        ctx.get_logger().info("Weather widget plugin uninstalled")
