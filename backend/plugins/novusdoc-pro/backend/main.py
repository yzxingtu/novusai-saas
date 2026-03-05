"""
NovusDoc Pro — 协作增强插件

商业版扩展：实时多人协作(Yjs)、评论批注、版本历史、文档权限、分享链接、Word/PDF 导出。
依赖: novusdoc (免费核心插件)
"""

from app.plugins.base import PluginBase


class NovusdocProPlugin(PluginBase):
    """NovusDoc Pro 插件主类"""

    async def on_install(self, ctx) -> None:
        logger = ctx.get_logger()
        logger.info("novusdoc-pro: install started")
        logger.info("novusdoc-pro: install completed")

    async def on_enable(self, ctx) -> None:
        logger = ctx.get_logger()

        try:
            import y_py  # noqa: F401
            logger.info("novusdoc-pro: enabled — collaboration features active")
        except ImportError:
            logger.warning(
                "novusdoc-pro: enabled in degraded mode — y-py not available; "
                "collaboration persistence is disabled for this runtime."
            )

    async def on_disable(self, ctx) -> None:
        logger = ctx.get_logger()
        logger.info("novusdoc-pro: disabled — collaboration features deactivated")

    async def on_uninstall(self, ctx) -> None:
        logger = ctx.get_logger()
        logger.info("novusdoc-pro: uninstall — collaboration data retained")

    async def on_upgrade(self, ctx, old_version: str) -> None:
        logger = ctx.get_logger()
        logger.info("novusdoc-pro: upgrade from %s to %s", old_version, ctx.manifest.version)
