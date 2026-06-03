"""知识库 API 共享辅助函数 / Shared helpers for knowledge base API."""

from __future__ import annotations

import hashlib
import json as json_lib
from collections.abc import Sequence
from typing import Any

from app.core.logging import get_logger
from app.enums.knowledge_base import DocumentTypeEnum

logger = get_logger(__name__)

ALLOWED_EXTENSIONS: dict[str, str] = {
    ".txt": DocumentTypeEnum.TXT.value,
    ".md": DocumentTypeEnum.MD.value,
    ".pdf": DocumentTypeEnum.PDF.value,
    ".docx": DocumentTypeEnum.DOCX.value,
    ".csv": DocumentTypeEnum.CSV.value,
    ".xlsx": DocumentTypeEnum.XLSX.value,
    ".html": DocumentTypeEnum.HTML.value,
    ".htm": DocumentTypeEnum.HTML.value,
    ".pptx": DocumentTypeEnum.PPTX.value,
    ".jpg": DocumentTypeEnum.IMAGE.value,
    ".jpeg": DocumentTypeEnum.IMAGE.value,
    ".png": DocumentTypeEnum.IMAGE.value,
    ".webp": DocumentTypeEnum.IMAGE.value,
    ".gif": DocumentTypeEnum.IMAGE.value,
    ".mp3": DocumentTypeEnum.AUDIO.value,
    ".wav": DocumentTypeEnum.AUDIO.value,
    ".m4a": DocumentTypeEnum.AUDIO.value,
    ".flac": DocumentTypeEnum.AUDIO.value,
    ".aac": DocumentTypeEnum.AUDIO.value,
    ".mp4": DocumentTypeEnum.VIDEO.value,
    ".webm": DocumentTypeEnum.VIDEO.value,
    ".mov": DocumentTypeEnum.VIDEO.value,
    ".avi": DocumentTypeEnum.VIDEO.value,
    ".mkv": DocumentTypeEnum.VIDEO.value,
}


def enrich_model_names(kb: Any, result: dict[str, Any]) -> None:
    """
    Enrich result dict with supported KB model name fields.
    将知识库当前公开支持的关联模型名称填充到 result 字典。
    """
    for key in (
        "audio_model_id",
        "audio_model_name",
        "video_model_id",
        "video_model_name",
    ):
        result.pop(key, None)
    for attr, key in [
        ("embedding_model", "embedding_model_name"),
        ("vision_model", "vision_model_name"),
    ]:
        result[key] = None
        try:
            model = getattr(kb, attr, None)
            if model:
                result[key] = model.name
        except Exception as exc:
            logger.debug("Knowledge base model name resolution failed: {}", exc)


async def load_kb_owner_tenant_name_map(
    db: Any,
    knowledge_bases: Sequence[Any],
) -> dict[int, str]:
    """Load owner tenant display names for a KB collection."""
    from sqlalchemy import select

    from app.models.tenant.tenant import Tenant

    owner_ids = {
        int(owner_tenant_id)
        for kb in knowledge_bases
        if (owner_tenant_id := getattr(kb, "owner_tenant_id", None)) is not None
    }
    if not owner_ids:
        return {}

    stmt = select(Tenant.id, Tenant.name).where(
        Tenant.id.in_(owner_ids),
        Tenant.is_deleted.is_(False),
    )
    rows = (await db.execute(stmt)).all()
    return {int(tenant_id): str(name) for tenant_id, name in rows}


async def serialize_selectable_knowledge_bases(
    db: Any,
    knowledge_bases: Sequence[Any],
) -> list[dict[str, Any]]:
    """Serialize compact selectable KB payloads with owner tenant metadata."""
    owner_name_map = await load_kb_owner_tenant_name_map(db, knowledge_bases)
    items: list[dict[str, Any]] = []
    for kb in knowledge_bases:
        owner_tenant_id = getattr(kb, "owner_tenant_id", None)
        items.append(
            {
                "id": kb.id,
                "name": kb.name,
                "description": kb.description,
                "scope": kb.scope,
                "document_count": kb.document_count,
                "owner_tenant_id": owner_tenant_id,
                "owner_tenant_name": (
                    owner_name_map.get(int(owner_tenant_id))
                    if owner_tenant_id is not None
                    else None
                ),
            }
        )
    return items


def build_content_hash(content: bytes | str) -> str:
    """Build a stable md5 content hash for KB documents."""
    raw = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.md5(raw, usedforsecurity=False).hexdigest()


def build_document_progress_payload(
    doc: Any,
    progress: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return live Redis progress when present, otherwise derive a DB fallback."""
    if progress is not None:
        return progress
    return {
        "stage": doc.status,
        "progress": 100 if doc.status == "completed" else 0,
        "total_chunks": doc.chunk_count,
        "processed_chunks": doc.chunk_count if doc.status == "completed" else 0,
    }


def build_qa_content(question: str, answer: str) -> str:
    """Build canonical Q&A content used by manual/batch KB imports."""
    return f"Q: {question}\nA: {answer}"


async def create_qa_document_and_chunk(
    *,
    db: Any,
    tenant_id: int | None,
    kb: Any,
    kb_id: int,
    question: str,
    answer: str,
    doc_service: Any,
    chunk_service: Any,
) -> Any:
    """Create a completed QA document and its single embedded chunk."""
    from app.ai.rag.embedding import EmbeddingService
    from app.ai.utils.token_estimator import estimate_tokens
    from app.enums.knowledge_base import DocumentStatusEnum, DocumentTypeEnum

    qa_content = build_qa_content(question, answer)
    content_hash = build_content_hash(qa_content)

    doc = await doc_service.create(
        {
            "knowledge_base_id": kb_id,
            "file_name": f"qa_{content_hash[:8]}.txt",
            "file_type": DocumentTypeEnum.QA.value,
            "file_size": len(qa_content.encode("utf-8")),
            "file_hash": content_hash,
            "status": DocumentStatusEnum.COMPLETED.value,
            "chunk_count": 1,
            "char_count": len(qa_content),
            "metadata_extra": json_lib.dumps({"question": question, "answer": answer}),
        }
    )

    embedding_service = EmbeddingService(db, tenant_id)
    embeddings = await embedding_service.generate_embedding(qa_content, kb)
    token_count = estimate_tokens(qa_content)

    await chunk_service.create(
        {
            "document_id": doc.id,
            "knowledge_base_id": kb_id,
            "chunk_index": 0,
            "content": qa_content,
            "content_hash": content_hash,
            "embedding": embeddings,
            "char_count": len(qa_content),
            "token_count": token_count,
            "metadata_": {
                "type": "qa",
                "question": question,
                "answer": answer,
            },
        }
    )
    doc.token_count = token_count
    return doc


async def create_url_import_documents(
    *,
    doc_service: Any,
    kb_id: int,
    urls: Sequence[str],
) -> list[dict[str, Any]]:
    """Create pending KB URL documents for valid, non-duplicate URLs."""
    from app.enums.knowledge_base import DocumentStatusEnum, DocumentTypeEnum

    created_docs: list[dict[str, Any]] = []
    for raw_url in urls:
        url = raw_url.strip()
        if not url or not url.startswith(("http://", "https://")):
            continue

        url_hash = build_content_hash(url)
        existing = await doc_service.get_by_kb_and_hash(kb_id, url_hash)
        if existing:
            continue

        doc = await doc_service.create(
            {
                "knowledge_base_id": kb_id,
                "file_name": url[:200],
                "file_type": DocumentTypeEnum.URL.value,
                "file_size": len(url.encode("utf-8")),
                "file_hash": url_hash,
                "source_url": url,
                "status": DocumentStatusEnum.PENDING.value,
                "metadata_extra": url,
            }
        )
        created_docs.append(doc.to_dict())
    return created_docs


async def enqueue_document_processing(
    *,
    tenant_id: int | None,
    document_ids: Sequence[int],
) -> None:
    """Queue KB document processing tasks for one or more document ids."""
    from app.ai.rag.processor import process_document

    for document_id in document_ids:
        process_document.delay(
            tenant_id=tenant_id,
            document_id=document_id,
        )


def resolve_document_type(filename: str) -> str | None:
    """Resolve KB document type from filename extension."""
    import os

    ext = os.path.splitext(filename)[1].lower()
    return ALLOWED_EXTENSIONS.get(ext)


def serialize_search_results(results: Sequence[Any]) -> list[dict[str, Any]]:
    """Serialize retriever result objects into API payloads."""
    return [
        {
            "chunk_id": item.chunk_id,
            "content": item.content,
            "score": item.score,
            "metadata": item.metadata,
            "document_name": item.document_name,
            "document_id": item.document_id,
            "highlight": item.highlight,
        }
        for item in results
    ]
