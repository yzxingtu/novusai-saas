"""
Amazon S3 Compatible Storage Plugin
"""

from app.plugins.base import PluginBase


class S3StoragePlugin(PluginBase):
    """S3 compatible storage driver plugin"""

    async def on_install(self, ctx) -> None:
        ctx.get_logger().info("S3 compatible storage plugin installed")

    async def on_enable(self, ctx) -> None:
        try:
            import boto3  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "Required package 'boto3' is not installed. "
                "Run: pip install 'boto3>=1.35'"
            )
        ctx.get_logger().info("S3 compatible storage plugin enabled")

    async def on_disable(self, ctx) -> None:
        ctx.get_logger().info("S3 compatible storage plugin disabled")

    async def on_uninstall(self, ctx) -> None:
        ctx.get_logger().info("S3 compatible storage plugin uninstalled")
