"""
Internal AI service.

Provides a thin, explicit internal entry point for platform and tenant AI
gateway calls without depending on synthetic system-agent records.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway import AIGateway
from app.ai.types import ChatMessage, ChatResponse, EmbeddingResponse
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.internal_service")


class InternalAIService:
    """
    Internal AI service / 内部 AI 服务

    This service replaces the legacy SystemAgentService bridge. Internal
    platform and tenant calls now route directly to AIGateway through a named
    infrastructure service instead of depending on fake "system agent" rows.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.gateway = AIGateway(db)

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
        logger.info(
            "Internal chat dispatch: model={}/{} tenant={}",
            provider_code, model, tenant_id,
        )
        return await self.gateway.chat(
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
        logger.info(
            "Internal stream chat dispatch: model={}/{} tenant={}",
            provider_code, model, tenant_id,
        )
        return await self.gateway.stream_chat(
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
        logger.info(
            "Internal embedding dispatch: model={}/{} tenant={}",
            provider_code, model, tenant_id,
        )
        return await self.gateway.embedding(
            provider_code=provider_code,
            texts=texts,
            model=model,
            tenant_id=tenant_id,
            user_id=user_id,
            user_type=user_type,
        )


__all__ = ["InternalAIService"]
