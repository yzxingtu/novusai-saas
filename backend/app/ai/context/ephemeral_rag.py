"""
Ephemeral RAG provider / 临时 RAG provider
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Any

from app.ai.rag.chunker import ChunkData, get_chunker
from app.ai.rag.parser import (
    CsvParser,
    HtmlParser,
    MarkdownParser,
    ParsedPage,
    TxtParser,
    UrlParser,
)
from app.ai.tools.security import SSRFBlockedError, UrlValidator
from app.ai.types import ChatMessage
from app.models.tenant.attachment import Attachment
from app.services.ai.ephemeral_document_service import EphemeralDocumentService
from app.services.common.storage_config_resolver import StorageConfigResolver
from app.storage.manager import storage_manager


@dataclass
class EphemeralRAGSource:
    doc_name: str
    doc_id: int
    score: float
    snippet: str
    source_kind: str = "ephemeral_doc"
    page: int | None = None
    heading: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "doc_name": self.doc_name,
            "doc_id": self.doc_id,
            "score": self.score,
            "snippet": self.snippet,
            "source_kind": self.source_kind,
        }
        if self.page is not None:
            payload["page"] = self.page
        if self.heading:
            payload["heading"] = self.heading
        return payload


class EphemeralRAGProvider:
    def __init__(self) -> None:
        self._txt_parser = TxtParser()
        self._html_parser = HtmlParser()
        self._markdown_parser = MarkdownParser()
        self._csv_parser = CsvParser()
        self._url_parser = UrlParser()
        self._max_attachment_bytes = 512 * 1024

    async def inject(
        self,
        *,
        messages: list[ChatMessage],
        ephemeral_rag_refs: list[dict[str, Any]],
        db: Any | None = None,
        tenant_id: int | None = None,
        conversation_id: int | None = None,
        agent_id: int | None = None,
        user_id: int | None = None,
    ) -> tuple[list[ChatMessage], list[dict[str, Any]]]:
        persisted_refs: list[dict[str, Any]] = []
        if db is not None and tenant_id is not None:
            try:
                service = EphemeralDocumentService(db, tenant_id)
                if ephemeral_rag_refs:
                    stored_docs = await service.upsert_refs(
                        conversation_id=conversation_id,
                        agent_id=agent_id,
                        user_id=user_id,
                        refs=ephemeral_rag_refs,
                    )
                    persisted_refs.extend(self._ephemeral_docs_to_refs(stored_docs))
                runtime_docs = await service.list_runtime_documents(
                    conversation_id=conversation_id,
                    agent_id=agent_id,
                    user_id=user_id,
                )
                persisted_refs.extend(self._ephemeral_docs_to_refs(runtime_docs))
            except Exception:
                persisted_refs = []

        attachment_refs = await self._build_attachment_refs(
            messages=messages,
            db=db,
            tenant_id=tenant_id,
        )
        merged_refs = self._dedupe_refs(
            [*(ephemeral_rag_refs or []), *persisted_refs, *attachment_refs]
        )
        if not merged_refs:
            return messages, []

        user_query = ""
        for message in reversed(messages):
            if message.role == "user" and (message.content or "").strip():
                user_query = message.content.strip()
                break
        if not user_query:
            return messages, []

        sources = await self._retrieve_sources(merged_refs, user_query)
        if not sources:
            return messages, []

        lines = ["[EPHEMERAL DOCUMENT CONTEXT]"]
        for index, source in enumerate(sources, start=1):
            lines.append(f"{index}. {source.doc_name}: {source.snippet}")

        messages[0].content = (messages[0].content or "").rstrip() + "\n\n" + "\n".join(lines)
        return messages, [source.to_dict() for source in sources]

    @staticmethod
    def _ephemeral_docs_to_refs(docs: list[Any]) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for doc in docs:
            content = str(getattr(doc, "content", "") or "").strip()
            if not content:
                continue
            refs.append(
                {
                    "kind": str(getattr(doc, "content_kind", "") or "text"),
                    "content": content,
                    "doc_id": getattr(doc, "id", None),
                    "title": str(getattr(doc, "title", "") or "").strip() or "Ephemeral Document",
                    "source_ref": getattr(doc, "source_ref", None),
                    "scope": getattr(doc, "scope_type", None),
                }
            )
        return refs

    @staticmethod
    def _dedupe_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for ref in refs:
            key = (
                str(ref.get("kind") or "").strip().lower(),
                str(ref.get("content") or "").strip(),
            )
            if not key[1] or key in seen:
                continue
            seen.add(key)
            deduped.append(ref)
        return deduped

    async def _retrieve_sources(
        self,
        refs: list[dict[str, Any]],
        query_text: str,
    ) -> list[EphemeralRAGSource]:
        query_terms = self._build_query_terms(query_text)
        if not query_terms:
            return []

        results: list[tuple[float, EphemeralRAGSource]] = []
        for idx, ref in enumerate(refs, start=1):
            kind = str(ref.get("kind") or "").strip().lower()
            content = str(ref.get("content") or "")
            if kind not in {"csv", "html", "markdown", "text", "url"} or not content.strip():
                continue
            title = (
                str(ref.get("title") or ref.get("source_ref") or f"Ephemeral Doc {idx}").strip()
                or f"Ephemeral Doc {idx}"
            )

            try:
                parsed_pages = await self._parse_ref(kind, content, title)
            except Exception:
                continue
            if not parsed_pages:
                continue
            chunker = get_chunker(strategy="semantic", chunk_size=700, chunk_overlap=80)
            chunks = chunker.chunk(parsed_pages)
            for chunk in chunks:
                score = self._score_chunk(chunk, query_terms)
                if score <= 0:
                    continue
                results.append(
                    (
                        score,
                        EphemeralRAGSource(
                            doc_name=title,
                            doc_id=int(ref.get("doc_id") or idx),
                            score=round(score, 4),
                            snippet=(chunk.content or "")[:280],
                            page=chunk.metadata.get("page"),
                            heading=chunk.metadata.get("heading"),
                        ),
                    )
                )

        results.sort(key=lambda item: item[0], reverse=True)
        top = [item[1] for item in results[:5]]
        return self._relevance_gap_filter(top)

    async def _parse_ref(
        self,
        kind: str,
        content: str,
        title: str,
    ) -> list[ParsedPage]:
        if kind == "url":
            try:
                await UrlValidator.validate(content)
            except SSRFBlockedError:
                return []
            stream = io.BytesIO(content.encode("utf-8"))
            return await self._url_parser.parse(stream, file_name=title)

        stream = io.BytesIO(content.encode("utf-8"))
        if kind == "html":
            return await self._html_parser.parse(stream, file_name=title)
        if kind == "markdown":
            return await self._markdown_parser.parse(stream, file_name=title)
        if kind == "csv":
            return await self._csv_parser.parse(stream, file_name=title)
        return await self._txt_parser.parse(stream, file_name=title)

    @staticmethod
    def _score_chunk(chunk: ChunkData, query_terms: set[str]) -> float:
        text = (chunk.content or "").lower()
        if not text:
            return 0.0
        matches = sum(1 for term in query_terms if term in text)
        if matches == 0:
            return 0.0
        density = matches / max(len(query_terms), 1)
        exact_boost = 0.15 if any(term in text for term in query_terms if len(term) >= 4) else 0.0
        return density + exact_boost

    @staticmethod
    def _build_query_terms(query_text: str) -> set[str]:
        normalized = " ".join((query_text or "").split()).lower()
        terms = {
            term.strip()
            for term in normalized.split(" ")
            if len(term.strip()) >= 2
        }

        cjk_sequences = re.findall(r"[\u4e00-\u9fff]{2,}", normalized)
        for seq in cjk_sequences:
            terms.add(seq)
            for width in (2, 3, 4):
                if len(seq) < width:
                    continue
                for idx in range(0, len(seq) - width + 1):
                    terms.add(seq[idx:idx + width])

        if not terms and normalized:
            compact = normalized.replace(" ", "")
            if len(compact) >= 2:
                terms.add(compact)

        return terms

    @staticmethod
    def _relevance_gap_filter(
        sources: list[EphemeralRAGSource],
    ) -> list[EphemeralRAGSource]:
        if len(sources) <= 1:
            return sources
        kept: list[EphemeralRAGSource] = [sources[0]]
        previous_score = sources[0].score
        for source in sources[1:]:
            if previous_score - source.score > 0.45:
                break
            kept.append(source)
            previous_score = source.score
        return kept

    async def _build_attachment_refs(
        self,
        *,
        messages: list[ChatMessage],
        db: Any | None,
        tenant_id: int | None,
    ) -> list[dict[str, Any]]:
        if db is None or tenant_id is None:
            return []

        refs: list[dict[str, Any]] = []
        attachment_ids: list[int] = []
        attachment_meta: dict[int, dict[str, Any]] = {}
        for message in messages:
            if message.role != "user":
                continue
            for attachment in message.attachments or []:
                attachment_id = attachment.get("attachment_id")
                if not isinstance(attachment_id, int) or attachment_id <= 0:
                    continue
                attachment_ids.append(attachment_id)
                attachment_meta[attachment_id] = attachment

        if not attachment_ids:
            return []

        for attachment_id in attachment_ids:
            ref = await self._attachment_to_ref(
                db=db,
                tenant_id=tenant_id,
                attachment_id=attachment_id,
                attachment_meta=attachment_meta.get(attachment_id) or {},
            )
            if ref:
                refs.append(ref)
        return refs

    async def _attachment_to_ref(
        self,
        *,
        db: Any,
        tenant_id: int,
        attachment_id: int,
        attachment_meta: dict[str, Any],
    ) -> dict[str, Any] | None:
        from sqlalchemy import select

        result = await db.execute(
            select(Attachment).where(
                Attachment.id == attachment_id,
                Attachment.is_deleted.is_(False),
            )
        )
        attachment = result.scalar_one_or_none()
        if not attachment:
            return None
        if attachment.tenant_id not in {tenant_id, None}:
            return None
        if int(getattr(attachment, "size", 0) or 0) > self._max_attachment_bytes:
            return None

        content_kind = self._infer_attachment_kind(attachment, attachment_meta)
        if content_kind is None:
            return None

        resolver = StorageConfigResolver(db)
        storage_config = await resolver.resolve_for_attachment_record(attachment)
        driver = storage_manager.get_driver(storage_config)
        content_stream = await driver.get(attachment.path)
        raw_bytes = content_stream.read()
        if not raw_bytes:
            return None

        try:
            content = raw_bytes.decode("utf-8", errors="replace")
        except Exception:
            return None

        title = (
            str(attachment_meta.get("name") or getattr(attachment, "original_name", None) or getattr(attachment, "name", "")).strip()
            or f"Attachment {attachment_id}"
        )
        return {
            "kind": content_kind,
            "doc_id": attachment_id,
            "title": title,
            "content": content,
            "source_ref": f"attachment:{attachment_id}",
        }

    @staticmethod
    def _infer_attachment_kind(
        attachment: Attachment,
        attachment_meta: dict[str, Any],
    ) -> str | None:
        mime_type = str(
            attachment_meta.get("mime_type")
            or getattr(attachment, "mime_type", None)
            or ""
        ).lower()
        name = str(
            attachment_meta.get("name")
            or getattr(attachment, "original_name", None)
            or getattr(attachment, "name", "")
        ).lower()

        if mime_type == "text/html" or name.endswith((".html", ".htm")):
            return "html"
        if mime_type in {"text/markdown", "text/x-markdown"} or name.endswith(
            (".md", ".markdown")
        ):
            return "markdown"
        if mime_type in {"text/csv", "application/csv"} or name.endswith(".csv"):
            return "csv"
        if mime_type.startswith("text/") or mime_type in {
            "application/json",
            "application/ld+json",
        } or name.endswith((".txt", ".json", ".log")):
            return "text"
        return None


__all__ = ["EphemeralRAGProvider", "EphemeralRAGSource"]
