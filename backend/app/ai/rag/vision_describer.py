"""
Vision Image Description Service
Vision 图片描述服务

Internal LLM call within RAG pipeline (exempt from AI architecture rules:
LLM calls inside RAG pipeline are part of Agent skill internal implementation,
not subject to Agent→Skill restrictions).
RAG 管道内部 LLM 调用（符合 AI 架构规则豁免：
RAG 管道内部的 LLM 调用属于 Agent 技能内部实现，不受 Agent→Skill 限制）。
"""

from __future__ import annotations

import asyncio
import base64
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.gateway import AIGateway
from app.ai.types import ChatMessage
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.ai import ModelTypeEnum

if TYPE_CHECKING:
    from app.models.ai.knowledge_base import KnowledgeBase
    from app.models.ai.model import AIModel

logger = LogManager.get_logger("ai.rag")

# Max single image size (20 MB) / 单张图片最大限制（20 MB）
_MAX_IMAGE_BYTES = 20 * 1024 * 1024

# Vision call timeout (seconds) / Vision 调用超时（秒）
_VISION_TIMEOUT_SECONDS = 30.0


class VisionDescriber:
    """
    Image Description Service (within RAG pipeline)
    图片描述服务（RAG 管道内部）

    Calls Vision model to generate text descriptions for images, used for subsequent text embedding.
    All exceptions are silently handled (returns ""), without interrupting document processing.
    调用 Vision 模型为图片生成文字描述，供后续 text embedding 使用。
    任何异常均静默处理（返回 ""），不中断文档处理流程。

    Vision model selection priority / Vision 模型选取优先级：
    1. knowledge_base.vision_model_id (admin explicit config) / 管理员显式配置
    2. First platform model with is_active=True & supports_vision=True & type='chat'
       平台第一个 is_active=True & supports_vision=True & type='chat' 的模型
    3. No available model → return "", log warning / 无可用模型 → 返回 ""，记录 warning

    tenant_id must be provided to ensure Vision API costs are attributed to the correct tenant.
    tenant_id 必须传入以确保 Vision API 成本归入对应租户。
    """

    def __init__(self, db: AsyncSession, tenant_id: int | None) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.gateway = AIGateway(db)

    async def describe_image(
        self,
        image_bytes: bytes,
        mime_type: str,
        knowledge_base: KnowledgeBase,
    ) -> str:
        """
        Generate text description for an image
        生成图片的文字描述

        Args:
            image_bytes: Image binary content / 图片二进制内容
            mime_type: MIME type (e.g. image/jpeg) / MIME 类型
            knowledge_base: KB object (with optional vision_model_id) / 知识库对象（含可选 vision_model_id 属性）

        Returns:
            Image text description string, returns "" on failure
            图片文字描述字符串，失败返回 ""
        """
        if not image_bytes:
            return ""

        if len(image_bytes) > _MAX_IMAGE_BYTES:
            logger.warning(
                "Image too large (%d bytes > %d), skipping vision description for KB %d",
                len(image_bytes),
                _MAX_IMAGE_BYTES,
                knowledge_base.id,
            )
            return ""

        model = await self._get_vision_model(knowledge_base)
        if not model:
            logger.warning(
                "No vision model available for KB %d, skipping image description",
                knowledge_base.id,
            )
            return ""

        provider = model.provider
        if not provider:
            logger.warning(
                "Vision model id=%d has no associated provider, skipping",
                model.id,
            )
            return ""

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64}"

        messages = [
            ChatMessage(
                role="user",
                content=_("knowledge_base.vision.describe_prompt"),
                attachments=[
                    {"type": "image", "url": data_url, "mime_type": mime_type}
                ],
            )
        ]

        try:
            response = await asyncio.wait_for(
                self.gateway.chat(
                    provider_code=provider.code,
                    messages=messages,
                    model=model.code,
                    temperature=0.3,
                    tenant_id=self.tenant_id,
                ),
                timeout=_VISION_TIMEOUT_SECONDS,
            )
            return (response.content or "").strip()

        except asyncio.TimeoutError:
            logger.warning(
                "Vision description timeout (%ds) for KB %d model=%s",
                int(_VISION_TIMEOUT_SECONDS),
                knowledge_base.id,
                model.code,
            )
            return ""

        except Exception as exc:
            logger.warning(
                "Vision description failed for KB %d model=%s: %s",
                knowledge_base.id,
                model.code,
                str(exc),
            )
            return ""

    async def _get_vision_model(
        self,
        knowledge_base: KnowledgeBase,
    ) -> AIModel | None:
        """
        Get Vision model / 获取 Vision 模型

        Priority / 优先级：
        1. knowledge_base.vision_model_id (exists after T3 migration) / T3 迁移后存在
        2. First enabled platform vision chat model / 平台第一个启用的 vision chat 模型
        """
        from app.models.ai.model import AIModel

        vision_model_id: int | None = getattr(knowledge_base, "vision_model_id", None)

        if vision_model_id:
            stmt = (
                select(AIModel)
                .where(
                    AIModel.id == vision_model_id,
                    AIModel.is_active.is_(True),
                    AIModel.is_deleted.is_(False),
                    AIModel.supports_vision.is_(True),
                )
                .options(selectinload(AIModel.provider))
            )
            result = await self.db.execute(stmt)
            model = result.scalar_one_or_none()
            if model:
                return model
            logger.warning(
                "Configured vision_model_id=%d not active/available, falling back to default",
                vision_model_id,
            )

        stmt = (
            select(AIModel)
            .where(
                AIModel.is_active.is_(True),
                AIModel.is_deleted.is_(False),
                AIModel.supports_vision.is_(True),
                AIModel.type == ModelTypeEnum.CHAT.value,
            )
            .options(selectinload(AIModel.provider))
            .order_by(AIModel.id.asc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


__all__ = ["VisionDescriber"]
