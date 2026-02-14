"""
重排序器

使用 LLM 对检索结果重新评分排序，提升精度
默认关闭，作为可选增强能力
"""

from __future__ import annotations

import json
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway import AIGateway
from app.ai.types import ChatMessage
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.rag.reranker")


class LLMReranker:
    """
    LLM 重排序器

    将 query + 每个 chunk 拼接发给 LLM 评分 1~10，
    根据评分重新排序结果。
    """

    SYSTEM_PROMPT = (
        "You are a relevance scoring assistant. "
        "Rate the relevance of the document excerpt to the query on a scale of 1-10.\n"
        "Output ONLY a JSON array of objects with 'index' (0-based) and 'score' (1-10).\n"
        "Example: [{\"index\": 0, \"score\": 8}, {\"index\": 1, \"score\": 3}]"
    )

    def __init__(self, db: AsyncSession, tenant_id: int, model: str | None = None):
        """
        Args:
            db: 数据库会话
            tenant_id: 租户 ID
            model: LLM 模型代码
        """
        self.db = db
        self.tenant_id = tenant_id
        self.gateway = AIGateway(db)
        self.model = model

    async def rerank(
        self,
        query: str,
        results: list,
        top_k: int | None = None,
    ) -> list:
        """
        使用 LLM 重排序检索结果

        Args:
            query: 原始查询
            results: ChunkSearchResult 列表
            top_k: 返回数量（None 时保留全部）

        Returns:
            重排序后的 ChunkSearchResult 列表
        """
        if not results:
            return results

        try:
            provider_code, model_code = await self._get_model_info()

            # 构建评分 prompt
            user_content = self._build_prompt(query, results)

            messages = [
                ChatMessage(role="system", content=self.SYSTEM_PROMPT),
                ChatMessage(role="user", content=user_content),
            ]

            response = await self.gateway.chat(
                provider_code=provider_code,
                messages=messages,
                model=model_code,
                temperature=0,
                max_tokens=1024,
                tenant_id=self.tenant_id,
            )

            # 解析评分
            scores = self._parse_scores(response.message.content, len(results))

            # 按评分重排序
            scored_results = []
            for idx, result in enumerate(results):
                score = scores.get(idx, 0)
                result.score = round(score / 10.0, 4)  # 归一化到 0-1
                scored_results.append((score, result))

            scored_results.sort(key=lambda x: x[0], reverse=True)
            reranked = [r for _, r in scored_results]

            if top_k:
                reranked = reranked[:top_k]

            logger.info(
                "LLM rerank: query='%s', input=%d, output=%d",
                query[:50], len(results), len(reranked),
            )

            return reranked

        except Exception as exc:
            logger.warning("LLM rerank failed, returning original: %s", str(exc))
            return results[:top_k] if top_k else results

    @staticmethod
    def _build_prompt(query: str, results: list) -> str:
        """构建评分请求 prompt"""
        parts = [f"Query: {query}\n\nDocument excerpts:"]
        for idx, r in enumerate(results):
            content_preview = r.content[:300]
            parts.append(f"\n[{idx}] {content_preview}")
        parts.append("\n\nRate each excerpt's relevance to the query (1-10):")
        return "\n".join(parts)

    @staticmethod
    def _parse_scores(content: str, count: int) -> dict[int, float]:
        """
        解析 LLM 返回的评分 JSON

        Returns:
            {index: score} 映射
        """
        scores: dict[int, float] = {}

        try:
            # 尝试直接解析 JSON
            json_match = re.search(r"\[.*\]", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                for item in data:
                    idx = int(item.get("index", -1))
                    score = float(item.get("score", 0))
                    if 0 <= idx < count:
                        scores[idx] = min(max(score, 1), 10)
        except (json.JSONDecodeError, ValueError, TypeError):
            # 回退：尝试逐行解析 "0: 8" 或 "[0] 8" 格式
            for line in content.split("\n"):
                match = re.search(r"[\[\(]?(\d+)[\]\)]?\s*[:=]\s*(\d+\.?\d*)", line)
                if match:
                    idx = int(match.group(1))
                    score = float(match.group(2))
                    if 0 <= idx < count:
                        scores[idx] = min(max(score, 1), 10)

        return scores

    async def _get_model_info(self) -> tuple[str, str]:
        """获取 LLM 模型信息"""
        from app.repositories.ai import AIModelRepository
        if self.model:
            model_repo = AIModelRepository(self.db)
            ai_model = await model_repo.get_by_code(self.model)
            if ai_model and ai_model.provider:
                return ai_model.provider.code, ai_model.code

        from app.core.config import settings
        return settings.DEFAULT_AI_PROVIDER, settings.DEFAULT_AI_MODEL


__all__ = ["LLMReranker"]
