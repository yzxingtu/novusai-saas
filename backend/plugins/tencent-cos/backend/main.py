"""
Tencent Cloud COS Storage Plugin
"""

from app.plugins.base import PluginBase


class CosStoragePlugin(PluginBase):
    """Tencent Cloud COS storage driver plugin"""

    async def on_install(self, ctx) -> None:
        ctx.get_logger().info("Tencent COS storage plugin installed")

    async def on_enable(self, ctx) -> None:
        try:
            from qcloud_cos import CosS3Client  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "Required package 'cos-python-sdk-v5' is not installed. "
                "Run: pip install 'cos-python-sdk-v5>=1.9'"
            )
        ctx.get_logger().info("Tencent COS storage plugin enabled")

    async def on_disable(self, ctx) -> None:
        ctx.get_logger().info("Tencent COS storage plugin disabled")

    async def on_uninstall(self, ctx) -> None:
        ctx.get_logger().info("Tencent COS storage plugin uninstalled")
