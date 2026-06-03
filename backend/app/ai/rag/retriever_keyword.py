"""
Keyword retrieval helpers for RAG.
"""

from __future__ import annotations

from sqlalchemy import Integer, String, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.retriever_types import ChunkSearchResult


class KeywordSearcher:
    """
    Keyword Searcher / 关键词检索器

    Uses PostgreSQL full-text search as the baseline, then boosts exact phrase,
    heading, filename and Chinese token matches.
    使用 PostgreSQL 全文检索作为基线，再叠加短语命中、标题命中、
    文件名命中和中文关键词命中增强。
    """

    _PUNCTUATION_CHARS = " \t\r\n，,。：:；;！？!?."
    _PREFIX_PHRASES = [
        "请你根据内部知识库",
        "请根据内部知识库",
        "麻烦你根据内部知识库",
        "帮我根据内部知识库",
        "请你在内部知识库中",
        "请在内部知识库中",
        "根据内部知识库",
        "based on the internal knowledge base",
        "answer based on the internal knowledge base",
        "respond based on the internal knowledge base",
        "please answer based on the internal knowledge base",
        "please explain using the internal knowledge base",
    ]
    _SUFFIX_PHRASES = [
        "请基于内部知识库回答",
        "请基于内部知识库",
        "请只基于内部知识回答",
        "请只基于内部知识库回答",
        "请只基于内部知识",
        "请只参考内部知识库",
        "请仅参考内部知识库",
        "请不要使用外部资料",
        "please answer based on the internal knowledge base only",
        "please do not use external sources",
        "please do not reference external information",
    ]
    _LEADING_FILLERS = [
        "请你回答",
        "麻烦你回答",
        "帮我回答",
        "请你说明",
        "麻烦你说明",
        "请你解释",
    ]

    def __init__(self, db: AsyncSession):
        self.db = db

    def _normalize_query(self, query: str) -> str:
        return " ".join((query or "").split())

    @staticmethod
    def _is_cjk(ch: str) -> bool:
        return "\u4e00" <= ch <= "\u9fff"

    @classmethod
    def _iter_query_segments(cls, query: str) -> list[str]:
        segments: list[str] = []
        i = 0
        length = len(query)
        while i < length:
            ch = query[i]
            if cls._is_cjk(ch):
                start = i
                while i < length and cls._is_cjk(query[i]):
                    i += 1
                segments.append(query[start:i])
                continue
            if ch.isalnum():
                start = i
                while i < length and (query[i].isalnum() or query[i] in "._-"):
                    i += 1
                segment = query[start:i]
                if segment:
                    segments.append(segment)
                continue
            i += 1
        return segments

    @classmethod
    def _extract_quoted_terms(cls, query: str) -> list[str]:
        terms: list[str] = []
        i = 0
        length = len(query)
        while i < length:
            ch = query[i]
            if ch in {'"', "'"}:
                quote = ch
                start = i + 1
                i += 1
                while i < length and query[i] != quote:
                    i += 1
                term = query[start:i].strip()
                if 2 <= len(term) <= 64:
                    terms.append(term)
                i += 1
                continue
            i += 1
        return terms

    @classmethod
    def _strip_candidates(
        cls,
        text: str,
        candidates: list[str],
        *,
        strip_start: bool,
    ) -> str:
        stripped = text
        while True:
            matched = False
            for candidate in candidates:
                candidate_lower = candidate.lower()
                working = stripped.lstrip(cls._PUNCTUATION_CHARS)
                lower = working.lower()
                if strip_start and lower.startswith(candidate_lower):
                    stripped = working[len(candidate) :]
                    stripped = stripped.lstrip(cls._PUNCTUATION_CHARS)
                    matched = True
                    break
                if not strip_start:
                    working = stripped.rstrip(cls._PUNCTUATION_CHARS)
                    lower = working.lower()
                    if lower.endswith(candidate_lower):
                        stripped = working[: -len(candidate)].rstrip(
                            cls._PUNCTUATION_CHARS
                        )
                        matched = True
                        break
            if not matched:
                break
        return stripped

    @classmethod
    def _strip_leading_fillers(cls, text: str) -> str:
        stripped = text
        for filler in cls._LEADING_FILLERS:
            if stripped.lower().startswith(filler):
                stripped = stripped[len(filler) :]
                stripped = stripped.lstrip(cls._PUNCTUATION_CHARS)
                break
        return stripped

    def _expand_tokens(self, query: str) -> list[str]:
        tokens: list[str] = []
        for segment in self._iter_query_segments(query):
            has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in segment)
            if has_cjk:
                if len(segment) >= 2:
                    tokens.append(segment)
                if len(segment) > 2:
                    tokens.extend(
                        segment[idx : idx + 2] for idx in range(len(segment) - 1)
                    )
            elif len(segment) >= 2:
                tokens.append(segment.lower())

        deduped: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            if token and token not in seen:
                seen.add(token)
                deduped.append(token)
        return deduped[:12]

    def _extract_exact_terms(self, query: str) -> list[str]:
        normalized = self._normalize_query(query)
        if not normalized:
            return []

        candidates: list[str] = []
        candidates.extend(self._extract_quoted_terms(normalized))

        for token in self._iter_query_segments(normalized):
            token = token.strip()
            if len(token) < 2:
                continue
            has_symbol = any(ch in token for ch in "._-:/#")
            has_digit = any(ch.isdigit() for ch in token)
            has_upper = any(ch.isupper() for ch in token)
            if has_symbol or has_digit or has_upper:
                candidates.append(token)

        deduped: list[str] = []
        seen: set[str] = set()
        for term in candidates:
            lowered = term.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            deduped.append(term)
        return deduped[:8]

    def _technical_term_boost(
        self,
        *,
        query: str,
        content: str,
        metadata: dict | None,
        document_name: str,
    ) -> float:
        exact_terms = self._extract_exact_terms(query)
        if not exact_terms:
            return 0.0

        haystacks = [
            (content or "").lower(),
            str((metadata or {}).get("heading") or "").lower(),
            (document_name or "").lower(),
        ]
        boost = 0.0
        for term in exact_terms:
            lowered = term.lower()
            if any(lowered in haystack for haystack in haystacks if haystack):
                boost += 0.18 if any(ch in term for ch in "._-:/#") else 0.1
        return min(boost, 0.72)

    async def search(
        self,
        kb_ids: list[int],
        query: str,
        limit: int = 10,
    ) -> list[ChunkSearchResult]:
        """
        Boosted keyword search / 增强型关键词检索。
        """
        normalized_query = self._normalize_query(query)
        if not normalized_query:
            return []

        tokens = self._expand_tokens(normalized_query)
        sql = text(
            """
            WITH search_input AS (
                SELECT
                    :raw_query AS raw_query,
                    :fts_query AS fts_query,
                    :tokens AS tokens
            ),
            ranked AS (
                SELECT
                    dc.id,
                    dc.content,
                    dc.document_id,
                    dc.chunk_index,
                    dc.metadata AS chunk_metadata,
                    dc.knowledge_base_id,
                    kd.file_name AS document_name,
                    CASE
                        WHEN si.fts_query <> ''
                             AND dc.content_tsv @@ plainto_tsquery('simple', si.fts_query)
                        THEN ts_rank(dc.content_tsv, plainto_tsquery('simple', si.fts_query))
                        ELSE 0
                    END AS fts_rank,
                    CASE
                        WHEN si.raw_query <> '' AND dc.content ILIKE '%' || si.raw_query || '%'
                        THEN 1 ELSE 0
                    END AS exact_hit,
                    CASE
                        WHEN si.raw_query <> ''
                             AND COALESCE(dc.metadata->>'heading', '') ILIKE '%' || si.raw_query || '%'
                        THEN 1 ELSE 0
                    END AS heading_hit,
                    CASE
                        WHEN si.raw_query <> '' AND kd.file_name ILIKE '%' || si.raw_query || '%'
                        THEN 1 ELSE 0
                    END AS filename_hit,
                    (
                        SELECT count(*)
                        FROM unnest(si.tokens) AS token
                        WHERE token <> ''
                          AND (
                              dc.content ILIKE '%' || token || '%'
                              OR COALESCE(dc.metadata->>'heading', '') ILIKE '%' || token || '%'
                              OR kd.file_name ILIKE '%' || token || '%'
                          )
                    ) AS token_hits
                FROM document_chunks dc
                JOIN knowledge_documents kd
                    ON kd.id = dc.document_id
                    AND kd.is_deleted = false
                    AND kd.status = 'completed'
                CROSS JOIN search_input si
                WHERE dc.knowledge_base_id = ANY(:kb_ids)
                    AND dc.is_deleted = false
                    AND (
                        (si.fts_query <> '' AND dc.content_tsv @@ plainto_tsquery('simple', si.fts_query))
                        OR (si.raw_query <> '' AND dc.content ILIKE '%' || si.raw_query || '%')
                        OR (si.raw_query <> '' AND COALESCE(dc.metadata->>'heading', '') ILIKE '%' || si.raw_query || '%')
                        OR (si.raw_query <> '' AND kd.file_name ILIKE '%' || si.raw_query || '%')
                        OR EXISTS (
                            SELECT 1
                            FROM unnest(si.tokens) AS token
                            WHERE token <> ''
                              AND (
                                  dc.content ILIKE '%' || token || '%'
                                  OR COALESCE(dc.metadata->>'heading', '') ILIKE '%' || token || '%'
                                  OR kd.file_name ILIKE '%' || token || '%'
                              )
                        )
                    )
            )
            SELECT
                id,
                content,
                document_id,
                chunk_index,
                chunk_metadata,
                knowledge_base_id,
                document_name,
                (
                    fts_rank
                    + exact_hit * 0.8
                    + heading_hit * 0.45
                    + filename_hit * 0.35
                    + LEAST(token_hits, :token_hit_cap) * :token_hit_weight
                ) AS rank
            FROM ranked
            ORDER BY rank DESC, exact_hit DESC, heading_hit DESC, token_hits DESC, id DESC
            LIMIT :limit
            """
        ).bindparams(
            bindparam("kb_ids", type_=ARRAY(Integer)),
            bindparam("tokens", type_=ARRAY(String)),
        )

        result = await self.db.execute(
            sql,
            {
                "raw_query": normalized_query,
                "fts_query": normalized_query,
                "tokens": tokens,
                "kb_ids": kb_ids,
                "limit": limit,
                "token_hit_cap": 6,
                "token_hit_weight": 0.08,
            },
        )
        rows = result.fetchall()

        results: list[ChunkSearchResult] = []
        for row in rows:
            boost = self._technical_term_boost(
                query=normalized_query,
                content=row[1] or "",
                metadata=row[4],
                document_name=row[6] or "",
            )
            rank = round(float(row[7]) + boost, 4)
            results.append(
                ChunkSearchResult(
                    chunk_id=row[0],
                    content=row[1],
                    score=rank,
                    raw_score=rank,
                    metadata=row[4],
                    document_name=row[6] or "",
                    document_id=row[2],
                    chunk_index=row[3],
                    knowledge_base_id=int(row[5] or 0),
                    recall_sources=["keyword"],
                )
            )

        return results


__all__ = ["KeywordSearcher"]
