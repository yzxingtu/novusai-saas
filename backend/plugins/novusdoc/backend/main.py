"""
NovusDoc — AI 文档编辑器插件

基于 Tiptap 的现代化富文本编辑器，支持文档管理、AI 写作助手、全文搜索。
免费社区版，novusdoc-pro 可扩展协作/评论/版本历史等商业功能。
"""

from app.plugins.base import PluginBase

# NovusDoc Writer 智能体的 system prompt
_WRITER_SYSTEM_PROMPT = (
    "你是 NovusDoc 写作助手，嵌入在一个富文本文档编辑器中。\n"
    "你的职责是帮助用户进行文档写作、优化、校对、翻译、摘要和扩写。\n"
    "请根据用户提供的文档上下文和指令，输出高质量的文本内容。\n"
    "注意事项：\n"
    "- 匹配用户文档的风格、语气和语言\n"
    "- 只输出结果文本，不要添加解释或说明\n"
    "- 保持专业、简洁、准确\n"
    "- 如果用户使用中文写作，用中文回复；英文则用英文"
)

# 智能体标识名称（用于查找已创建的智能体）
_WRITER_AGENT_NAME = "NovusDoc Writer"


class NovusdocPlugin(PluginBase):
    """NovusDoc 插件主类"""

    async def on_install(self, ctx) -> None:
        logger = ctx.get_logger()
        logger.info("novusdoc: install started")
        logger.info("novusdoc: install completed")

    async def on_enable(self, ctx) -> None:
        logger = ctx.get_logger()
        logger.info("novusdoc: enabled")

        db = ctx._db
        try:
            agent_id = await self._ensure_writer_agent(db, logger)
            if agent_id:
                await self._bind_ai_features(db, ctx.plugin_name, agent_id, logger)
                await db.flush()
                logger.info("novusdoc: AI agent (id=%d) created and features bound", agent_id)
            else:
                logger.warning("novusdoc: no AI model available, skipping agent creation")
        except Exception as exc:
            logger.warning("novusdoc: failed to setup AI agent (non-fatal): %s", exc)

    async def on_disable(self, ctx) -> None:
        logger = ctx.get_logger()
        logger.info("novusdoc: disabled")

    async def on_uninstall(self, ctx) -> None:
        logger = ctx.get_logger()
        logger.info("novusdoc: uninstall started — plugin data retained in DB")
        logger.info("novusdoc: uninstall completed")

    async def on_upgrade(self, ctx, old_version: str) -> None:
        logger = ctx.get_logger()
        logger.info("novusdoc: upgrade from %s to %s", old_version, ctx.manifest.version)

    # ── Private helpers ──

    @staticmethod
    async def _ensure_writer_agent(db, logger) -> int | None:
        """
        确保 NovusDoc Writer 智能体存在。
        如果已存在则返回 id，否则自动创建。
        如果无可用 AI 模型则返回 None。
        """
        from sqlalchemy import select
        from app.models.ai.agent import Agent
        from app.models.ai.model import AIModel

        # 检查是否已存在
        existing = await db.execute(
            select(Agent.id).where(
                Agent.name == _WRITER_AGENT_NAME,
                Agent.is_deleted.is_(False),
            )
        )
        agent_id = existing.scalar_one_or_none()
        if agent_id:
            logger.info("novusdoc: writer agent already exists (id=%d)", agent_id)
            return agent_id

        # 查找第一个可用的 chat 模型（排除 embedding 模型）
        model_result = await db.execute(
            select(AIModel.id, AIModel.name).where(
                AIModel.is_deleted.is_(False),
                AIModel.name.notin_(["text-embedding-v3", "text-embedding-ada-002"]),
            ).limit(1)
        )
        model_row = model_result.first()
        if not model_row:
            return None

        model_id = model_row[0]
        logger.info("novusdoc: creating writer agent with model %s (id=%d)", model_row[1], model_id)

        from app.enums.agent import AgentStatusEnum, AgentExecutionModeEnum
        from app.enums.common import ResourceScopeEnum

        agent = Agent(
            name=_WRITER_AGENT_NAME,
            description="NovusDoc 插件专用写作助手，负责文档续写、优化、校对、翻译等 AI 功能。",
            model_id=model_id,
            system_prompt=_WRITER_SYSTEM_PROMPT,
            scope=ResourceScopeEnum.ALL_TENANTS.value,
            status=AgentStatusEnum.PUBLISHED.value,
            execution_mode=AgentExecutionModeEnum.CONVERSATION.value,
            temperature=0.7,
            max_tokens=2048,
            tenant_id=None,
            is_system=True,
        )
        db.add(agent)
        await db.flush()
        return agent.id

    @staticmethod
    async def _bind_ai_features(db, plugin_name: str, agent_id: int, logger) -> None:
        """
        将插件的 AI features 绑定到指定智能体。
        只更新 agent_id 为 null 的记录（不覆盖管理员手动绑定）。
        """
        from sqlalchemy import select, update
        from app.models.system.agent_assignment import SystemAgentAssignment

        prefix = f"plugin.{plugin_name}."
        result = await db.execute(
            select(SystemAgentAssignment.id, SystemAgentAssignment.feature_code).where(
                SystemAgentAssignment.feature_code.like(f"{prefix}%"),
                SystemAgentAssignment.agent_id.is_(None),
                SystemAgentAssignment.is_deleted.is_(False),
            )
        )
        rows = result.all()
        if not rows:
            logger.info("novusdoc: all AI features already bound or none registered")
            return

        ids_to_update = [row[0] for row in rows]
        await db.execute(
            update(SystemAgentAssignment)
            .where(SystemAgentAssignment.id.in_(ids_to_update))
            .values(agent_id=agent_id)
        )
        logger.info(
            "novusdoc: bound %d AI features to agent %d: %s",
            len(ids_to_update), agent_id,
            [row[1] for row in rows],
        )
