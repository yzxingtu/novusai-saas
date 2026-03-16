"""
Audio Description Service (within RAG pipeline) / RAG 管道内音频描述服务

Converts audio to text for subsequent embedding. Exceptions are silently handled (returns "").
Real ASR integration (e.g. Whisper) can be added later; this stub returns placeholder so pipeline runs.
将音频转为文本供后续 embedding。异常静默处理（返回 ""）。
实际 ASR（如 Whisper）可后续接入；当前占位实现保证管道可运行。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import LogManager
from app.enums.ai import ModelTypeEnum

if TYPE_CHECKING:
    from app.models.ai.knowledge_base import KnowledgeBase
    from app.models.ai.model import AIModel

logger = LogManager.get_logger("ai.rag")

# Max single audio size (50 MB) / 单条音频最大限制（50 MB）
_MAX_AUDIO_BYTES = 50 * 1024 * 1024


class AudioDescriber:
    """
    Audio-to-text service for RAG pipeline. / RAG 管道内音频转文本服务。

    When ASR is integrated, call platform ASR or knowledge_base.audio_model_id.
    For now returns empty string so audio documents are skipped (no content to embed).
    ASR 接入后可调用平台 ASR 或 knowledge_base.audio_model_id。
    当前返回空字符串，音频文档不产生可嵌入内容。
    """

    def __init__(self, db: AsyncSession, tenant_id: int | None) -> None:
        self.db = db
        self.tenant_id = tenant_id

    async def describe_audio(
        self,
        audio_bytes: bytes,
        mime_type: str,
        knowledge_base: KnowledgeBase | None = None,
    ) -> str:
        """
        Generate text from audio (ASR). Placeholder: returns "" until ASR is integrated.
        从音频生成文本（ASR）。占位：在接入 ASR 前返回 ""。

        Args:
            audio_bytes: Audio binary content / 音频二进制
            mime_type: MIME type (e.g. audio/mpeg) / MIME 类型
            knowledge_base: Optional KB (for audio_model_id later) / 可选知识库（后续用于 audio_model_id）

        Returns:
            Transcribed text, or "" on failure / 转写文本，失败返回 ""
        """
        if not audio_bytes:
            return ""
        if len(audio_bytes) > _MAX_AUDIO_BYTES:
            logger.warning(
                "Audio too large ({} bytes > {}), skipping",
                len(audio_bytes),
                _MAX_AUDIO_BYTES,
            )
            return ""
        model = await self._get_audio_model(knowledge_base)
        if not model:
            logger.debug(
                "No audio model available for KB {}, skipping ASR",
                getattr(knowledge_base, "id", None) if knowledge_base else None,
            )
            return ""
        # Placeholder: no ASR yet; return empty so processor filters this page
        # 占位：尚未接入 ASR；返回空字符串，processor 会过滤该页
        logger.info(
            "Audio describer placeholder: mime={}, size={}, model={}",
            mime_type,
            len(audio_bytes),
            model.code,
        )
        return ""

    async def _get_audio_model(
        self,
        knowledge_base: KnowledgeBase | None,
    ) -> AIModel | None:
        """获取音频（ASR）模型：优先知识库 audio_model_id，再平台首个 supports_audio 的 chat 模型 / Get Audio (ASR) model: KB audio_model_id first, then first platform chat model with supports_audio."""
        from app.models.ai.model import AIModel

        audio_model_id: int | None = (
            getattr(knowledge_base, "audio_model_id", None) if knowledge_base else None
        )
        if audio_model_id:
            stmt = (
                select(AIModel)
                .where(
                    AIModel.id == audio_model_id,
                    AIModel.is_active.is_(True),
                    AIModel.is_deleted.is_(False),
                    AIModel.supports_audio.is_(True),
                )
                .options(selectinload(AIModel.provider))
            )
            result = await self.db.execute(stmt)
            model = result.scalar_one_or_none()
            if model:
                return model
            logger.warning(
                "Configured audio_model_id={} not active/available, falling back to default",
                audio_model_id,
            )
        stmt = (
            select(AIModel)
            .where(
                AIModel.is_active.is_(True),
                AIModel.is_deleted.is_(False),
                AIModel.supports_audio.is_(True),
                AIModel.type == ModelTypeEnum.CHAT.value,
            )
            .options(selectinload(AIModel.provider))
            .order_by(AIModel.id.asc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


__all__ = ["AudioDescriber"]
