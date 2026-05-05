"""
Shared helpers for retrieval orchestration.
"""

from __future__ import annotations

from app.ai.rag.retriever_keyword import KeywordSearcher
from app.ai.rag.retriever_types import ChunkSearchResult, SearchKBContext
from app.models.ai.knowledge_base import KnowledgeBase


def normalize_retrieval_query(query: str) -> str:
    normalized = " ".join((query or "").split())
    if not normalized:
        return ""

    # Remove retrieval wrappers so recall focuses on the user's core question.
    # 去掉“基于内部知识库回答”等包装语，避免污染检索 query。
    stripped = normalized
    stripped = KeywordSearcher._strip_candidates(
        stripped, KeywordSearcher._PREFIX_PHRASES, strip_start=True
    )
    stripped = KeywordSearcher._strip_candidates(
        stripped, KeywordSearcher._SUFFIX_PHRASES, strip_start=False
    )
    stripped = KeywordSearcher._strip_leading_fillers(stripped)
    stripped = stripped.strip(KeywordSearcher._PUNCTUATION_CHARS)
    return stripped or normalized


def build_kb_contexts(
    *,
    knowledge_base: KnowledgeBase | None,
    knowledge_bases: list[KnowledgeBase] | None,
    kb_weights: dict[int, float] | None,
) -> list[SearchKBContext]:
    kb_list = knowledge_bases or (
        [knowledge_base] if knowledge_base is not None else []
    )
    contexts: list[SearchKBContext] = []
    seen: set[int] = set()
    for kb in kb_list:
        kb_id = int(getattr(kb, "id", 0) or 0)
        if kb_id <= 0 or kb_id in seen:
            continue
        seen.add(kb_id)
        contexts.append(
            SearchKBContext(
                knowledge_base=kb,
                weight=float((kb_weights or {}).get(kb_id, 1.0)),
            )
        )
    return contexts


def relevance_gap_filter(
    results: list[ChunkSearchResult],
    *,
    max_drop: float = 0.32,
    min_keep: int = 1,
) -> list[ChunkSearchResult]:
    if len(results) <= min_keep:
        return results

    kept: list[ChunkSearchResult] = []
    previous_score: float | None = None
    for index, result in enumerate(results):
        if index < min_keep:
            kept.append(result)
            previous_score = float(result.score or 0.0)
            continue
        current_score = float(result.score or 0.0)
        if previous_score is not None and previous_score - current_score > max_drop:
            break
        kept.append(result)
        previous_score = current_score
    return kept


__all__ = ["normalize_retrieval_query", "build_kb_contexts", "relevance_gap_filter"]
