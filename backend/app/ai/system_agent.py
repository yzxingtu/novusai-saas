"""
System Agent Service
系统 Agent 服务

Provides a unified entry point for system-level Agent calls.
All external AI calls (chat / embedding) are routed through this service,
no longer directly instantiating AIGateway.
提供系统级 Agent 的统一调用入口。
所有外部 AI 调用（chat / embedding）均通过此服务路由，
不再直接实例化 AIGateway。

Architecture / 架构：Controller → SystemAgentService → AIGateway
      (External API / 外部 API)   (System Agent auth layer / 系统 Agent 授权层)  (AI engine impl / AI 引擎实现)

SystemAgentService is the explicitly allowed AI call entry point in ai-architecture.md,
using system Agent verification as an auth gateway, then delegating to AIGateway.
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
    System Agent Service / 系统 Agent 服务

    Dispatches AI capabilities through system Agent, replacing direct AIGateway calls from controllers.
    System Agent serves as the unified entry point and auth gateway for all external AI requests.
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
        Get and verify system Agent.
        获取并验证系统 Agent。

        Returns:
            Agent instance / Agent 实例

        Raises:
            NotFoundException: System Agent not found / 系统 Agent 不存在
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
        user_type: str | None = None,
    ) -> ChatResponse:
        """
        Call LLM chat via system chat Agent (non-streaming). / 通过系统聊天 Agent 调用 LLM 聊天（非流式）。

        System Agent verification → AIGateway.chat
        系统 Agent 验证 → AIGateway.chat
        """
        agent = await self._get_system_agent(self.CHAT_AGENT_NAME)

        logger.info(
            "System chat dispatch: agent_id={} model={}/{} tenant={}",
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
            user_type=user_type,
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
        user_type: str | None = None,
    ):
        """
        Call streaming LLM chat via system chat Agent. / 通过系统聊天 Agent 调用流式 LLM 聊天。

        System Agent verification → AIGateway.stream_chat
        系统 Agent 验证 → AIGateway.stream_chat
        """
        agent = await self._get_system_agent(self.CHAT_AGENT_NAME)

        logger.info(
            "System stream chat dispatch: agent_id={} model={}/{} tenant={}",
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
            user_type=user_type,
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
        user_id: int | None = None,
        user_type: str | None = None,
    ) -> EmbeddingResponse:
        """
        Call embedding via system Embedding Agent. / 通过系统 Embedding Agent 调用向量化。

        System Agent verification → AIGateway.embedding
        系统 Agent 验证 → AIGateway.embedding
        """
        agent = await self._get_system_agent(self.EMBEDDING_AGENT_NAME)

        logger.info(
            "System embedding dispatch: agent_id={} model={}/{} tenant={}",
            agent.id, provider_code, model, tenant_id,
        )

        gateway = AIGateway(self.db)
        return await gateway.embedding(
            provider_code=provider_code,
            texts=texts,
            model=model,
            tenant_id=tenant_id,
            user_id=user_id,
            user_type=user_type,
        )


__all__ = ["SystemAgentService"]
