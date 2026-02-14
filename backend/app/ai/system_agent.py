"""
系统 Agent 服务

提供系统级 Agent 的统一调用入口。
所有外部 AI 调用（chat / embedding）均通过此服务路由，
不再直接实例化 AIGateway。

架构：Controller → SystemAgentService → AIGateway
      (外部 API)   (系统 Agent 授权层)  (AI 引擎实现)

SystemAgentService 是 ai-architecture.md 中明确允许的 AI 调用入口，
通过系统 Agent 验证作为授权网关，再委托 AIGateway 完成实际调用。
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway import AIGateway
from app.ai.types import ChatMessage, ChatResponse, EmbeddingResponse
from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import NotFoundException
from app.models.ai.agent import Agent

logger = LogManager.get_logger("ai.system_agent")


class SystemAgentService:
    """
    系统 Agent 服务

    通过系统 Agent 调度 AI 能力，替代控制器直接调用 AIGateway。
    系统 Agent 作为所有外部 AI 请求的统一入口和授权网关。

    Usage::

        service = SystemAgentService(db)
        result = await service.chat(provider_code=..., messages=..., model=...)
        result = await service.embedding(provider_code=..., texts=..., model=...)
    """

    CHAT_AGENT_NAME = "system_chat_agent"
    EMBEDDING_AGENT_NAME = "system_embedding_agent"

    def __init__(self, db: AsyncSession):
        self.db = db
        self._agent_cache: dict[str, Agent] = {}

    async def _get_system_agent(self, name: str) -> Agent:
        """
        获取并验证系统 Agent

        Returns:
            Agent 实例

        Raises:
            NotFoundException: 系统 Agent 不存在
        """
        if name in self._agent_cache:
            return self._agent_cache[name]

        stmt = (
            select(Agent)
            .where(Agent.name == name)
            .where(Agent.is_system.is_(True))
            .where(Agent.is_deleted.is_(False))
        )
        result = await self.db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            raise NotFoundException(
                message=_("agent.error.system_agent_not_found")
            )

        self._agent_cache[name] = agent
        return agent

    # ========================================
    # Chat
    # ========================================

    async def chat(
        self,
        *,
        provider_code: str,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
        tenant_id: int | None = None,
        user_id: int | None = None,
    ) -> ChatResponse:
        """
        通过系统聊天 Agent 调用 LLM 聊天（非流式）

        系统 Agent 验证 → AIGateway.chat
        """
        agent = await self._get_system_agent(self.CHAT_AGENT_NAME)

        logger.info(
            "System chat dispatch: agent_id=%d model=%s/%s tenant=%s",
            agent.id, provider_code, model, tenant_id,
        )

        gateway = AIGateway(self.db)
        return await gateway.chat(
            provider_code=provider_code,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stream=stream,
            tools=tools,
            tenant_id=tenant_id,
            user_id=user_id,
        )

    async def stream_chat(
        self,
        *,
        provider_code: str,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        tools: list[dict[str, Any]] | None = None,
        tenant_id: int | None = None,
        user_id: int | None = None,
    ):
        """
        通过系统聊天 Agent 调用流式 LLM 聊天

        系统 Agent 验证 → AIGateway.stream_chat
        """
        agent = await self._get_system_agent(self.CHAT_AGENT_NAME)

        logger.info(
            "System stream chat dispatch: agent_id=%d model=%s/%s tenant=%s",
            agent.id, provider_code, model, tenant_id,
        )

        gateway = AIGateway(self.db)
        return await gateway.stream_chat(
            provider_code=provider_code,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tenant_id=tenant_id,
            user_id=user_id,
        )

    # ========================================
    # Embedding
    # ========================================

    async def embedding(
        self,
        *,
        provider_code: str,
        texts: list[str],
        model: str,
        tenant_id: int | None = None,
    ) -> EmbeddingResponse:
        """
        通过系统 Embedding Agent 调用向量化

        系统 Agent 验证 → AIGateway.embedding
        """
        agent = await self._get_system_agent(self.EMBEDDING_AGENT_NAME)

        logger.info(
            "System embedding dispatch: agent_id=%d model=%s/%s tenant=%s",
            agent.id, provider_code, model, tenant_id,
        )

        gateway = AIGateway(self.db)
        return await gateway.embedding(
            provider_code=provider_code,
            texts=texts,
            model=model,
            tenant_id=tenant_id,
        )


__all__ = ["SystemAgentService"]
