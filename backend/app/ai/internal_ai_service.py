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
from app.enums.ai import CallTypeEnum

logger = LogManager.get_logger("ai.internal_service")


class InternalAIService:
    """
    Internal AI service / 内部 AI 服务

    Internal platform and tenant calls route directly to AIGateway through a
    named infrastructure service instead of depending on synthetic agent rows.
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
        call_type: str = CallTypeEnum.MAIN_CHAT.value,
    ) -> ChatResponse:
        logger.info(
            "Internal chat dispatch: model={}/{} tenant={}",
            provider_code,
            model,
            tenant_id,
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
            call_type=call_type,
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
        call_type: str = CallTypeEnum.MAIN_CHAT.value,
    ):
        logger.info(
            "Internal stream chat dispatch: model={}/{} tenant={}",
            provider_code,
            model,
            tenant_id,
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
            call_type=call_type,
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
        call_type: str = CallTypeEnum.MAIN_CHAT.value,
    ) -> EmbeddingResponse:
        logger.info(
            "Internal embedding dispatch: model={}/{} tenant={}",
            provider_code,
            model,
            tenant_id,
        )
        return await self.gateway.embedding(
            provider_code=provider_code,
            texts=texts,
            model=model,
            tenant_id=tenant_id,
            user_id=user_id,
            user_type=user_type,
            call_type=call_type,
        )


__all__ = ["InternalAIService"]
