"""
NovusDoc — AI 文档编辑器插件

基于 Tiptap 的现代化富文本编辑器，支持文档管理、AI 写作助手、全文搜索。
免费社区版，novusdoc-pro 可扩展协作/评论/版本历史等商业功能。

AI 功能说明：
  plugin.yaml 中声明的 ai_requirements.features 在安装时由框架自动创建
  SystemAgentAssignment 记录（agent_id=NULL）。管理员通过「插件详情 → AI 功能」
  面板将智能体绑定到各 feature_code，插件 API handler 中通过
  ctx.call_ai_feature("ai_writer", messages) 调用。
"""

from app.plugins.base import PluginBase


class NovusdocPlugin(PluginBase):
    """NovusDoc 插件主类"""

    async def on_install(self, ctx) -> None:
        logger = ctx.get_logger()
        logger.info("novusdoc: installed")

    async def on_enable(self, ctx) -> None:
        logger = ctx.get_logger()
        logger.info("novusdoc: enabled")

    async def on_disable(self, ctx) -> None:
        logger = ctx.get_logger()
        logger.info("novusdoc: disabled")

    async def on_uninstall(self, ctx) -> None:
        logger = ctx.get_logger()
        logger.info("novusdoc: uninstalled — plugin data retained in DB")

    async def on_upgrade(self, ctx, old_version: str) -> None:
        logger = ctx.get_logger()
        logger.info("novusdoc: upgrade from %s to %s", old_version, ctx.manifest.version)
