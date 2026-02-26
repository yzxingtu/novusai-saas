"""
Alibaba Cloud OSS Storage Plugin
"""

from app.plugins.base import PluginBase


class OssStoragePlugin(PluginBase):
    """Alibaba Cloud OSS storage driver plugin"""

    async def on_install(self, ctx) -> None:
        ctx.get_logger().info("Aliyun OSS storage plugin installed")

    async def on_enable(self, ctx) -> None:
        try:
            import alibabacloud_oss_v2  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "Required package 'alibabacloud-oss-v2' is not installed. "
                "Run: pip install 'alibabacloud-oss-v2>=1.0.0'"
            )
        ctx.get_logger().info("Aliyun OSS storage plugin enabled")

    async def on_disable(self, ctx) -> None:
        ctx.get_logger().info("Aliyun OSS storage plugin disabled")

    async def on_uninstall(self, ctx) -> None:
        ctx.get_logger().info("Aliyun OSS storage plugin uninstalled")
