"""
Query Rewriter / 查询改写器

Improves retrieval recall: rewrites user questions into multi-angle queries or hypothetical answers.
Disabled by default, serves as optional enhancement capability.
提升检索召回率：将用户问题改写为多角度查询或假设性回答。
默认关闭，作为可选增强能力。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway import AIGateway
from app.ai.types import ChatMessage
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.rag.query_rewriter")


class BaseRewriter(ABC):
    """Base rewriter class / 改写器基类"""

    @abstractmethod
    async def rewrite(self, query: str) -> list[str]:
        """
        Rewrite query / 改写查询

        Args:
            query: Original query / 原始查询

        Returns:
            Rewritten query list (includes original) / 改写后的查询列表（含原始查询）
        """


class NoneRewriter(BaseRewriter):
    """No-op rewriter (returns original query directly) / 空改写器（直接返回原始查询）"""

    async def rewrite(self, query: str) -> list[str]:
        return [query]


class MultiQueryRewriter(BaseRewriter):
    """
    Multi-Query Rewriter / 多查询改写器

    Calls LLM to rewrite user question into 3 queries from different angles,
    improving retrieval recall.
    调用 LLM 将用户问题改写为 3 个不同角度的查询，提升检索召回率。
    """

    SYSTEM_PROMPT = (
        "You are a search query optimizer. Given a user question, "
        "generate 3 different search queries that approach the question "
        "from different angles. Output ONLY the 3 queries, one per line, "
        "without numbering or extra text."
    )

    def __init__(self, db: AsyncSession, tenant_id: int, model: str | None = None):
        """
        Args:
            db: Database session / 数据库会话
            tenant_id: Tenant ID / 企业 ID
            model: LLM model code (None for default) / LLM 模型代码（None 时使用默认）
        """
        self.db = db
        self.tenant_id = tenant_id
        self.gateway = AIGateway(db)
        self.model = model

    async def rewrite(self, query: str) -> list[str]:
        """
        Generate 3 rewritten queries from different angles. / 生成 3 个不同角度的改写查询。

        Returned list always includes the original query.
        返回列表始终包含原始查询。
        """
        queries = [query]

        try:
            provider_code, model_code = await self._get_model_info()

            messages = [
                ChatMessage(role="system", content=self.SYSTEM_PROMPT),
                ChatMessage(role="user", content=query),
            ]

            response = await self.gateway.chat(
                provider_code=provider_code,
                messages=messages,
                model=model_code,
                temperature=0.7,
                max_tokens=256,
                tenant_id=self.tenant_id,
            )

            # Parse multi-line output / 解析多行输出
            lines = [
                line.strip()
                for line in response.message.content.strip().split("\n")
                if line.strip()
            ]
            for line in lines[:3]:
                if line != query:
                    queries.append(line)

            logger.info(
                "MultiQuery rewrite: '{}' → {} queries",
                query[:50],
                len(queries),
            )

        except Exception as exc:
            logger.warning("MultiQuery rewrite failed: {}", str(exc))

        return queries

    async def _get_model_info(self) -> tuple[str, str]:
        """Get LLM model info / 获取 LLM 模型信息"""
        from app.repositories.ai import AIModelRepository

        if self.model:
            model_repo = AIModelRepository(self.db)
            ai_model = await model_repo.get_by_code(self.model)
            if ai_model and ai_model.provider:
                return ai_model.provider.code, ai_model.code

        # Fallback to default model / 回退到默认模型
        from app.core.config import settings

        return settings.DEFAULT_AI_PROVIDER, settings.DEFAULT_AI_MODEL


class HyDERewriter(BaseRewriter):
    """
    HyDE（假设性文档嵌入）改写器 / HyDE (Hypothetical Document Embedding) Rewriter.

    Has LLM generate a hypothetical answer, then uses it for retrieval,
    since hypothetical answers are typically closer to target document semantics
    than short questions.
    让 LLM 生成一个假设性回答，用假设回答进行检索，
    因为假设回答通常比简短问题更接近目标文档的语义。
    """

    SYSTEM_PROMPT = (
        "You are a helpful assistant. Given a user question, "
        "write a brief hypothetical answer (1-2 paragraphs) as if "
        "you found the answer in a document. Do NOT say 'I don't know'. "
        "Just write the hypothetical content directly."
    )

    def __init__(self, db: AsyncSession, tenant_id: int, model: str | None = None):
        self.db = db
        self.tenant_id = tenant_id
        self.gateway = AIGateway(db)
        self.model = model

    async def rewrite(self, query: str) -> list[str]:
        """
        生成假设性回答作为检索查询 / Generate hypothetical answer as retrieval query.

        Returns [original query, hypothetical answer].
        返回 [原始查询, 假设性回答]。
        """
        queries = [query]

        try:
            provider_code, model_code = await self._get_model_info()

            messages = [
                ChatMessage(role="system", content=self.SYSTEM_PROMPT),
                ChatMessage(role="user", content=query),
            ]

            response = await self.gateway.chat(
                provider_code=provider_code,
                messages=messages,
                model=model_code,
                temperature=0.5,
                max_tokens=512,
                tenant_id=self.tenant_id,
            )

            hypothetical = response.message.content.strip()
            if hypothetical and hypothetical != query:
                queries.append(hypothetical)

            logger.info(
                "HyDE rewrite: '{}' → hypothetical len={}",
                query[:50],
                len(hypothetical),
            )

        except Exception as exc:
            logger.warning("HyDE rewrite failed: {}", str(exc))

        return queries

    async def _get_model_info(self) -> tuple[str, str]:
        """Get LLM model info / 获取 LLM 模型信息"""
        from app.repositories.ai import AIModelRepository

        if self.model:
            model_repo = AIModelRepository(self.db)
            ai_model = await model_repo.get_by_code(self.model)
            if ai_model and ai_model.provider:
                return ai_model.provider.code, ai_model.code

        from app.core.config import settings

        return settings.DEFAULT_AI_PROVIDER, settings.DEFAULT_AI_MODEL


def get_rewriter(
    strategy: str,
    db: AsyncSession,
    tenant_id: int,
    model: str | None = None,
) -> BaseRewriter:
    """
    Factory function: get rewriter instance by strategy name
    工厂函数：根据策略名获取改写器实例

    Args:
        strategy: Rewrite strategy (none/multi/hyde) / 改写策略
        db: Database session / 数据库会话
        tenant_id: Tenant ID / 企业 ID
        model: LLM model code / LLM 模型代码

    Returns:
        Rewriter instance / 改写器实例
    """
    from app.enums.knowledge_base import RewriteStrategyEnum

    if strategy == RewriteStrategyEnum.MULTI.value:
        return MultiQueryRewriter(db, tenant_id, model)
    elif strategy == RewriteStrategyEnum.HYDE.value:
        return HyDERewriter(db, tenant_id, model)
    else:
        return NoneRewriter()


__all__ = [
    "BaseRewriter",
    "NoneRewriter",
    "MultiQueryRewriter",
    "HyDERewriter",
    "get_rewriter",
]
