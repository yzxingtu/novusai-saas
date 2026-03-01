"""
Qiniu Kodo Storage Plugin
"""

from app.plugins.base import PluginBase


class KodoStoragePlugin(PluginBase):
    """Qiniu Kodo storage driver plugin"""

    async def on_install(self, ctx) -> None:
        ctx.get_logger().info("Qiniu Kodo storage plugin installed")

    async def on_enable(self, ctx) -> None:
        try:
            import qiniu  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "Required package 'qiniu' is not installed. "
                "Run: pip install 'qiniu>=7.14'"
            )
        ctx.get_logger().info("Qiniu Kodo storage plugin enabled")

    async def on_disable(self, ctx) -> None:
        ctx.get_logger().info("Qiniu Kodo storage plugin disabled")

    async def on_uninstall(self, ctx) -> None:
        ctx.get_logger().info("Qiniu Kodo storage plugin uninstalled")
