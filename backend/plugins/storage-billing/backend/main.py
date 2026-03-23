"""Storage billing plugin entrypoint. / 对象存储对账计费插件入口。"""

from app.plugins.base import PluginBase


class StorageBillingPlugin(PluginBase):
    """Storage billing reconciliation plugin. / 对象存储对账计费插件。"""

    async def on_install(self, ctx) -> None:
        ctx.get_logger().info("Storage billing plugin installed")

    async def on_enable(self, ctx) -> None:
        ctx.get_logger().info("Storage billing plugin enabled")

    async def on_disable(self, ctx) -> None:
        ctx.get_logger().info("Storage billing plugin disabled")

    async def on_uninstall(self, ctx) -> None:
        ctx.get_logger().info("Storage billing plugin uninstalled")
