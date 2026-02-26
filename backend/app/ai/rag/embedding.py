"""
Embedding 生成服务

封装 AI 网关的 Embedding 接口，提供单条和批量生成能力
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway import AIGateway
from app.ai.rag.text_cleaner import clean_for_embedding
from app.ai.types import EmbeddingResponse
from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.knowledge_base import KnowledgeBase

logger = LogManager.get_logger("ai.rag.embedding")

# 默认批量大小
DEFAULT_BATCH_SIZE = 100


class EmbeddingService:
    """
    Embedding 生成服务

    通过 AI 网关调用 Embedding 模型，支持单条和批量生成。
    自动从知识库配置获取模型和供应商信息。
    """

    def __init__(self, db: AsyncSession, tenant_id: int | None):
        """
        初始化

        Args:
            db: 数据库会话
            tenant_id: 租户 ID
        """
        self.db = db
        self.tenant_id = tenant_id
        self.gateway = AIGateway(db)

    async def generate_embedding(
        self,
        text: str,
        knowledge_base: KnowledgeBase,
    ) -> list[float]:
        """
        为单条文本生成 Embedding 向量

        Args:
            text: 待嵌入的文本
            knowledge_base: 知识库对象（含 embedding_model 关系）

        Returns:
            Embedding 向量（float 列表）

        Raises:
            BusinessException: 模型或供应商未配置
        """
        provider_code, model_code = self._resolve_model(knowledge_base)

        cleaned = clean_for_embedding(text)

        response = await self.gateway.embedding(
            provider_code=provider_code,
            texts=[cleaned],
            model=model_code,
            tenant_id=self.tenant_id,
        )

        if not response.embeddings:
            raise BusinessException(message=_("ai.error.embedding_empty_result"))

        return response.embeddings[0]

    async def batch_generate(
        self,
        texts: list[str],
        knowledge_base: KnowledgeBase,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> tuple[list[list[float]], int]:
        """
        批量生成 Embedding 向量

        按 batch_size 分批调用 AI 网关，避免单次请求超限。

        Args:
            texts: 文本列表
            knowledge_base: 知识库对象
            batch_size: 每批文本数量

        Returns:
            (embeddings, total_tokens): 向量列表和总消耗 token 数

        Raises:
            BusinessException: 模型或供应商未配置
        """
        if not texts:
            return [], 0

        provider_code, model_code = self._resolve_model(knowledge_base)

        all_embeddings: list[list[float]] = []
        total_tokens = 0

        for i in range(0, len(texts), batch_size):
            batch = [clean_for_embedding(t) for t in texts[i:i + batch_size]]

            response = await self.gateway.embedding(
                provider_code=provider_code,
                texts=batch,
                model=model_code,
                tenant_id=self.tenant_id,
            )

            all_embeddings.extend(response.embeddings)
            total_tokens += response.total_tokens or 0

            logger.info(
                "Embedding batch %d/%d (%d texts)",
                min(i + batch_size, len(texts)),
                len(texts),
                len(batch),
            )

        return all_embeddings, total_tokens

    @staticmethod
    def _resolve_model(knowledge_base: KnowledgeBase) -> tuple[str, str]:
        """
        从知识库配置解析 Embedding 模型信息

        Returns:
            (provider_code, model_code)

        Raises:
            BusinessException: 模型或供应商未配置
        """
        embedding_model = knowledge_base.embedding_model
        if not embedding_model:
            raise BusinessException(
                message=_("ai.error.embedding_model_not_configured")
            )

        provider = embedding_model.provider
        if not provider:
            raise BusinessException(
                message=_("ai.error.embedding_provider_not_found")
            )

        return provider.code, embedding_model.code


__all__ = ["EmbeddingService"]
