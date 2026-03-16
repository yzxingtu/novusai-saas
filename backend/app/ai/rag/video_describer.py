"""
Video Description Service (within RAG pipeline) / RAG 管道内视频描述服务

Converts video to text (e.g. keyframes + vision, or video understanding API). Exceptions return "".
Real integration can use keyframe extraction + VisionDescriber or vendor video API; this stub returns "".
将视频转为文本（如关键帧+视觉描述或视频理解 API）。异常返回 ""。
实际可接入关键帧+VisionDescriber 或厂商视频 API；当前占位返回 ""。
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

# Max single video size (100 MB) / 单条视频最大限制（100 MB）
_MAX_VIDEO_BYTES = 100 * 1024 * 1024


class VideoDescriber:
    """
    Video-to-text service for RAG pipeline. / RAG 管道内视频转文本服务。

    When integrated, may use keyframes + VisionDescriber or vendor video understanding API.
    For now returns empty string so video documents are skipped.
    接入后可使用关键帧+VisionDescriber 或厂商视频理解 API。当前返回 ""。
    """

    def __init__(self, db: AsyncSession, tenant_id: int | None) -> None:
        self.db = db
        self.tenant_id = tenant_id

    async def describe_video(
        self,
        video_bytes: bytes,
        mime_type: str,
        knowledge_base: KnowledgeBase | None = None,
    ) -> str:
        """
        Generate text description from video. Placeholder: returns "" until integration.
        从视频生成文本描述。占位：在接入前返回 ""。

        Args:
            video_bytes: Video binary content / 视频二进制
            mime_type: MIME type (e.g. video/mp4) / MIME 类型
            knowledge_base: Optional KB (for video_model_id later) / 可选知识库（后续用于 video_model_id）

        Returns:
            Description text, or "" on failure / 描述文本，失败返回 ""
        """
        if not video_bytes:
            return ""
        if len(video_bytes) > _MAX_VIDEO_BYTES:
            logger.warning(
                "Video too large ({} bytes > {}), skipping",
                len(video_bytes),
                _MAX_VIDEO_BYTES,
            )
            return ""
        model = await self._get_video_model(knowledge_base)
        if not model:
            logger.debug(
                "No video model available for KB {}, skipping video description",
                getattr(knowledge_base, "id", None) if knowledge_base else None,
            )
            return ""
        # Placeholder: no video understanding yet
        # 占位：尚未接入视频理解
        logger.info(
            "Video describer placeholder: mime={}, size={}, model={}",
            mime_type,
            len(video_bytes),
            model.code,
        )
        return ""

    async def _get_video_model(
        self,
        knowledge_base: KnowledgeBase | None,
    ) -> AIModel | None:
        """获取视频模型：优先知识库 video_model_id，再平台首个 supports_video 的 chat 模型 / Get Video model: KB video_model_id first, then first platform chat model with supports_video."""
        from app.models.ai.model import AIModel

        video_model_id: int | None = (
            getattr(knowledge_base, "video_model_id", None) if knowledge_base else None
        )
        if video_model_id:
            stmt = (
                select(AIModel)
                .where(
                    AIModel.id == video_model_id,
                    AIModel.is_active.is_(True),
                    AIModel.is_deleted.is_(False),
                    AIModel.supports_video.is_(True),
                )
                .options(selectinload(AIModel.provider))
            )
            result = await self.db.execute(stmt)
            model = result.scalar_one_or_none()
            if model:
                return model
            logger.warning(
                "Configured video_model_id={} not active/available, falling back to default",
                video_model_id,
            )
        stmt = (
            select(AIModel)
            .where(
                AIModel.is_active.is_(True),
                AIModel.is_deleted.is_(False),
                AIModel.supports_video.is_(True),
                AIModel.type == ModelTypeEnum.CHAT.value,
            )
            .options(selectinload(AIModel.provider))
            .order_by(AIModel.id.asc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


__all__ = ["VideoDescriber"]
