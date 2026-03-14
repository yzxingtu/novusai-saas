"""
NovusDoc plugin entry point / NovusDoc 插件入口
"""

from app.plugins.base import PluginBase


class NovusDocPlugin(PluginBase):
    async def on_install(self, ctx):
        logger = ctx.get_logger()
        logger.info("NovusDoc plugin installed")

    async def on_enable(self, ctx):
        logger = ctx.get_logger()
        logger.info("NovusDoc plugin enabled")

    async def on_disable(self, ctx):
        logger = ctx.get_logger()
        logger.info("NovusDoc plugin disabled")

    async def on_uninstall(self, ctx):
        logger = ctx.get_logger()
        logger.info("NovusDoc plugin uninstalled")
