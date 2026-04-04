"""
Reranker / 重排序器

Uses LLM to re-score and reorder retrieval results, improving precision.
Disabled by default, serves as optional enhancement capability.
使用 LLM 对检索结果重新评分排序，提升精度。
默认关闭，作为可选增强能力。
"""

from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway import AIGateway
from app.ai.prompt_contracts import render_prompt_contract
from app.ai.text_semantics import extract_first_json_array, parse_index_score_pair
from app.ai.types import ChatMessage
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.rag.reranker")


class LLMReranker:
    """
    LLM Reranker / LLM 重排序器

    Sends query + each chunk to LLM for scoring 1~10,
    then reorders results by score.
    将 query + 每个 chunk 拼接发给 LLM 评分 1~10，根据评分重新排序结果。
    """

    SYSTEM_PROMPT = render_prompt_contract("rag_reranker_system")

    def __init__(self, db: AsyncSession, tenant_id: int, model: str | None = None):
        """
        Args:
            db: Database session / 数据库会话
            tenant_id: Tenant ID / 企业 ID
            model: LLM model code / LLM 模型代码
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
        Rerank retrieval results using LLM
        使用 LLM 重排序检索结果

        Args:
            query: Original query / 原始查询
            results: ChunkSearchResult list / ChunkSearchResult 列表
            top_k: Number to return (None keeps all) / 返回数量（None 时保留全部）

        Returns:
            Reranked ChunkSearchResult list / 重排序后的 ChunkSearchResult 列表
        """
        if not results:
            return results

        try:
            provider_code, model_code = await self._get_model_info()

            # Build scoring prompt / 构建评分 prompt
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

            # Parse scores / 解析评分
            scores = self._parse_scores(response.message.content, len(results))

            # Reorder by score / 按评分重排序
            scored_results = []
            for idx, result in enumerate(results):
                score = scores.get(idx, 0)
                result.score = round(score / 10.0, 4)  # Normalize to 0-1 / 归一化到 0-1
                scored_results.append((score, result))

            scored_results.sort(key=lambda x: x[0], reverse=True)
            reranked = [r for _, r in scored_results]

            if top_k:
                reranked = reranked[:top_k]

            logger.info(
                "LLM rerank: query='{}', input={}, output={}",
                query[:50],
                len(results),
                len(reranked),
            )

            return reranked

        except Exception as exc:
            logger.warning("LLM rerank failed, returning original: {}", str(exc))
            return results[:top_k] if top_k else results

    @staticmethod
    def _build_prompt(query: str, results: list) -> str:
        """Build scoring request prompt / 构建评分请求 prompt"""
        return render_prompt_contract(
            "rag_reranker_user",
            query=query,
            excerpts=[
                {"index": idx, "content": (getattr(r, "content", "") or "")[:300]}
                for idx, r in enumerate(results)
            ],
        )

    @staticmethod
    def _parse_scores(content: str, count: int) -> dict[int, float]:
        """
        Parse LLM returned scoring JSON
        解析 LLM 返回的评分 JSON

        Returns:
            {index: score} mapping / {index: score} 映射
        """
        scores: dict[int, float] = {}

        try:
            # Try direct JSON parsing / 尝试直接解析 JSON
            data = extract_first_json_array(content)
            if data is not None:
                for item in data:
                    idx = int(item.get("index", -1))
                    score = float(item.get("score", 0))
                    if 0 <= idx < count:
                        scores[idx] = min(max(score, 1), 10)
        except (json.JSONDecodeError, ValueError, TypeError):
            # Fallback: try line-by-line parsing "0: 8" or "[0] 8" format
            # 回退：尝试逐行解析 "0: 8" 或 "[0] 8" 格式
            for line in content.split("\n"):
                pair = parse_index_score_pair(line)
                if pair is None:
                    continue
                idx, score = pair
                if 0 <= idx < count:
                    scores[idx] = min(max(score, 1), 10)

        return scores

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


__all__ = ["LLMReranker"]
