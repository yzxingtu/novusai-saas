"""
Celery Async Document Processing Task / Celery 异步文档处理任务

Processing flow: Parse → Chunk → Embedding → Store → Update statistics
Supports checkpoint resume (recover from error_stage) and Redis progress reporting.
处理流程：解析 → 分块 → Embedding → 存储 → 更新统计
支持断点续传（从 error_stage 恢复）和 Redis 进度上报
"""

from __future__ import annotations

import asyncio

from app.ai.rag.processor_document_support import load_and_parse_document
from app.core.base_model import utc_now
from app.core.logging import LogManager
from app.tasks.base import TenantTask, register_task

logger = LogManager.get_logger("ai.rag.processor")

# Redis progress key template, TTL 1 hour / Redis 进度 Key 模板，TTL 1 小时
PROGRESS_KEY_TEMPLATE = "kb:doc:progress:{document_id}"
PROGRESS_TTL = 3600


async def _report_progress(
    document_id: int,
    stage: str,
    progress: int,
    total_chunks: int = 0,
    processed_chunks: int = 0,
    *,
    tenant_id: int | None = None,
    kb_id: int | None = None,
) -> None:
    """Report processing progress to Redis + WS push / 上报处理进度到 Redis + WS 推送"""
    progress_data = {
        "stage": stage,
        "progress": min(progress, 100),
        "total_chunks": total_chunks,
        "processed_chunks": processed_chunks,
    }
    try:
        from app.core.redis import cache_set

        key = PROGRESS_KEY_TEMPLATE.format(document_id=document_id)
        await cache_set(key, progress_data, ttl=PROGRESS_TTL)
    except Exception:
        pass

    # WS real-time push (forwarded via Redis Pub/Sub in Celery sync environment)
    # WS 实时推送（Celery 同步环境通过 Redis Pub/Sub 转发）
    try:
        from app.core.sio_bridge import notify_admins_sync, notify_tenant_sync

        ws_payload = {
            "type": "ai.kb_doc_progress",
            "data": {
                "document_id": document_id,
                "kb_id": kb_id,
                **progress_data,
            },
        }
        if tenant_id is not None:
            notify_tenant_sync(tenant_id, ws_payload)
        else:
            notify_admins_sync(ws_payload)
    except Exception:
        pass


async def _clear_progress(document_id: int) -> None:
    """Clear Redis progress data / 清除 Redis 进度数据"""
    try:
        from app.core.redis import cache_delete

        key = PROGRESS_KEY_TEMPLATE.format(document_id=document_id)
        await cache_delete(key)
    except Exception:
        pass


async def get_document_progress(document_id: int) -> dict | None:
    """
    Get document processing progress (for API calls). / 获取文档处理进度（供 API 调用）。

    Reads from Redis first, returns None if no data available.
    优先读 Redis，如果无数据返回 None
    """
    from app.core.redis import cache_get

    key = PROGRESS_KEY_TEMPLATE.format(document_id=document_id)
    return await cache_get(key)


@register_task(
    queue="ai_gateway",
    description="Async knowledge base document processing (Parse→Chunk→Embedding→Store) / 异步处理知识库文档（解析→分块→Embedding→存储）",
    max_retries=3,
    base=TenantTask,
    soft_time_limit=600,
    time_limit=660,
    acks_late=True,
)
def process_document(self: TenantTask, tenant_id: int | None, document_id: int) -> dict:
    """
    Document processing main task (supports checkpoint resume)
    文档处理主任务（支持断点续传）

    Checkpoint resume mechanism / 断点续传机制：
    - error_stage='parsing' → Restart from parsing stage / 从解析阶段重新开始
    - error_stage='chunking' → Start from chunking stage / 从分块阶段开始
    - error_stage='embedding' → Continue from last successful chunk_index / 从上次成功的 chunk_index 继续

    Reports Redis progress in real-time for each stage, cleared upon completion.
    每个阶段实时上报 Redis 进度，完成后清除。

    Args:
        tenant_id: Tenant ID / 企业 ID
        document_id: Document ID / 文档 ID

    Returns:
        Processing result summary / 处理结果摘要
    """

    async def _execute() -> dict:
        from sqlalchemy import select

        # Clean up DB connections left from previous event loop (required for Windows --pool=solo)
        # 清理上一次 event loop 残留的 DB 连接（Windows --pool=solo 必需）
        from app.core.database import async_engine

        await async_engine.dispose()

        # Ensure AI adapters are registered (Celery worker may not have loaded registrations from celery_app.py)
        # 确保 AI 适配器已注册（Celery worker 可能未加载 celery_app.py 中的注册）
        from app.ai.adapters import AdapterRegistry, register_core_adapters

        if not AdapterRegistry.list_adapters():
            register_core_adapters()
            logger.info("Registered AI adapters in task context")

        from app.ai.gateway import AIGateway
        from app.ai.rag.chunker import get_chunker
        from app.ai.rag.embedding_resume_support import (
            EmbeddedChunkSnapshot,
            build_chunk_rows,
            plan_embedding_resume,
            validate_embedding_batch_count,
        )
        from app.core.database import async_session_factory
        from app.enums.knowledge_base import DocumentStatusEnum
        from app.models.ai.document_chunk import DocumentChunk
        from app.repositories.ai.knowledge_base_repository import (
            DocumentChunkRepository,
            KnowledgeBaseRepository,
            KnowledgeDocumentRepository,
        )

        async with async_session_factory() as db:
            try:
                # ===== 1. Load document and knowledge base / 加载文档和知识库 =====
                doc_repo = KnowledgeDocumentRepository(db, tenant_id)
                doc = await doc_repo.get_by_id(document_id)
                if not doc:
                    logger.error("Document {} not found", document_id)
                    return {"error": "Document not found"}

                kb_repo = KnowledgeBaseRepository(db, tenant_id)
                kb = await kb_repo.get_by_id(doc.knowledge_base_id)
                if not kb:
                    logger.error("KnowledgeBase {} not found", doc.knowledge_base_id)
                    return {"error": "KnowledgeBase not found"}

                # Checkpoint resume: check error_stage to determine starting stage
                # 断点续传：检查 error_stage 决定起始阶段
                resume_stage = doc.error_stage  # None = start from beginning / 从头开始
                skip_parsing = resume_stage in ("chunking", "embedding")
                skip_chunking = resume_stage == "embedding"

                logger.info(
                    "Processing document {} (type={}, kb={}, resume={})",
                    document_id,
                    doc.file_type,
                    kb.id,
                    resume_stage or "full",
                )

                # Reset error information / 重置错误信息
                doc.error_message = None
                doc.error_stage = None
                if not doc.processing_started_at:
                    doc.processing_started_at = utc_now()
                await db.commit()

                pages = None
                chunk_data_list = None

                # ===== 2. Parsing stage / 解析阶段 =====
                if not skip_parsing:
                    doc.status = DocumentStatusEnum.PARSING.value
                    await db.commit()
                    await _report_progress(
                        document_id, "parsing", 0, tenant_id=tenant_id, kb_id=kb.id
                    )

                    pages = await load_and_parse_document(db, doc, tenant_id, kb=kb)

                    await _report_progress(
                        document_id, "parsing", 100, tenant_id=tenant_id, kb_id=kb.id
                    )

                    if not pages:
                        logger.warning("Document {} parsed with 0 pages", document_id)

                # ===== 3. Chunking stage / 分块阶段 =====
                if not skip_chunking:
                    doc.status = DocumentStatusEnum.CHUNKING.value
                    await db.commit()
                    await _report_progress(
                        document_id, "chunking", 0, tenant_id=tenant_id, kb_id=kb.id
                    )

                    # If parsing was skipped (resuming from chunking), re-parse is needed
                    # 如果跳过了解析（从 chunking 恢复），需要重新解析
                    if pages is None:
                        pages = await load_and_parse_document(db, doc, tenant_id, kb=kb)

                    chunker = get_chunker(
                        strategy=kb.chunk_strategy,
                        chunk_size=kb.chunk_size,
                        chunk_overlap=kb.chunk_overlap,
                    )
                    chunk_data_list = chunker.chunk(pages or [])
                    await _report_progress(
                        document_id, "chunking", 100, tenant_id=tenant_id, kb_id=kb.id
                    )

                # ===== 4. Embedding stage (supports checkpoint resume) / Embedding 阶段（支持断点续传） =====
                doc.status = DocumentStatusEnum.EMBEDDING.value
                await db.commit()

                gateway = AIGateway(db)
                embedding_model = kb.embedding_model
                if not embedding_model:
                    raise ValueError("Embedding model not configured")
                provider = embedding_model.provider
                if not provider:
                    raise ValueError("Embedding model provider not found")

                # Checkpoint resume: if resuming from embedding stage, query existing chunk count
                # 断点续传：如果从 embedding 阶段恢复，查询已有分块数
                existing_chunk_count = 0
                if skip_chunking:
                    # Need to regenerate chunk_data_list (resuming from embedding)
                    # 需要重新生成 chunk_data_list（从 embedding 恢复）
                    if chunk_data_list is None:
                        # Re-parse + chunk (skip already completed embedding parts)
                        # 重新解析+分块（跳过 embedding 阶段已完成的部分）
                        pages = await load_and_parse_document(db, doc, tenant_id, kb=kb)

                        chunker = get_chunker(
                            strategy=kb.chunk_strategy,
                            chunk_size=kb.chunk_size,
                            chunk_overlap=kb.chunk_overlap,
                        )
                        chunk_data_list = chunker.chunk(pages or [])

                    # Query successfully written chunk fingerprint prefix (for checkpoint resume)
                    # 查询已成功写入分块指纹前缀（用于断点续传校验）
                    existing_stmt = (
                        select(
                            DocumentChunk.chunk_index,
                            DocumentChunk.content_hash,
                        )
                        .where(
                            DocumentChunk.document_id == document_id,
                            DocumentChunk.knowledge_base_id == kb.id,
                            DocumentChunk.is_deleted.is_(False),
                            DocumentChunk.embedding.isnot(None),
                        )
                        .order_by(DocumentChunk.chunk_index.asc())
                    )
                    existing_result = await db.execute(existing_stmt)
                    existing_chunks = [
                        EmbeddedChunkSnapshot(
                            chunk_index=int(row.chunk_index),
                            content_hash=str(row.content_hash or ""),
                        )
                        for row in existing_result
                    ]
                    resume_plan = plan_embedding_resume(
                        chunk_data_list=chunk_data_list,
                        existing_chunks=existing_chunks,
                    )
                    existing_chunk_count = resume_plan.existing_chunk_count
                    if resume_plan.restart_required:
                        logger.warning(
                            "Embedding resume fingerprint mismatch, restarting from chunk 0 for doc {}",
                            document_id,
                        )
                    logger.info(
                        "Resuming embedding from chunk {}/{} for doc {}",
                        existing_chunk_count,
                        len(chunk_data_list),
                        document_id,
                    )

                if chunk_data_list is None:
                    chunk_data_list = []

                total_chunks = len(chunk_data_list)
                total_char_count = sum(c.char_count for c in chunk_data_list)

                # Start Embedding from checkpoint position / 从断点位置开始 Embedding
                chunks_to_embed = chunk_data_list[existing_chunk_count:]
                # Read embedding_batch_size from provider config, default 10 (DashScope limit)
                # 从供应商配置读取 embedding_batch_size，默认 10（DashScope 限制）
                embedding_batch_size = 10
                if provider.config and isinstance(provider.config, dict):
                    embedding_batch_size = provider.config.get(
                        "embedding_batch_size", 10
                    )
                batch_size = min(embedding_batch_size, len(chunks_to_embed) or 1)
                all_embeddings: list[list[float]] = []
                total_token_count = 0
                processed_so_far = existing_chunk_count

                await _report_progress(
                    document_id,
                    "embedding",
                    int(processed_so_far / max(total_chunks, 1) * 100),
                    total_chunks,
                    processed_so_far,
                    tenant_id=tenant_id,
                    kb_id=kb.id,
                )

                from app.ai.rag.text_cleaner import clean_for_embedding

                for i in range(0, len(chunks_to_embed), batch_size):
                    batch = chunks_to_embed[i : i + batch_size]
                    texts = [clean_for_embedding(c.content) for c in batch]

                    response = await gateway.embedding(
                        provider_code=provider.code,
                        texts=texts,
                        model=embedding_model.code,
                        tenant_id=tenant_id,
                    )

                    validate_embedding_batch_count(
                        texts=texts,
                        embeddings=response.embeddings,
                    )
                    all_embeddings.extend(response.embeddings)
                    total_token_count += response.total_tokens or 0
                    processed_so_far += len(batch)

                    # Report progress / 上报进度
                    await _report_progress(
                        document_id,
                        "embedding",
                        int(processed_so_far / max(total_chunks, 1) * 100),
                        total_chunks,
                        processed_so_far,
                        tenant_id=tenant_id,
                        kb_id=kb.id,
                    )

                    logger.info(
                        "Embedding {}/{} for doc {}",
                        processed_so_far,
                        total_chunks,
                        document_id,
                    )

                # ===== 5. Batch write document_chunks / 批量写入 document_chunks =====
                chunk_repo = DocumentChunkRepository(db, tenant_id)

                if existing_chunk_count == 0:
                    # Fresh processing: delete old chunks first / 全新处理：先删除旧分块
                    await chunk_repo.delete_by_document(document_id, soft=False)

                # Only write newly generated chunks / 只写入新生成的分块
                write_batch_size = 500
                for i in range(0, len(chunks_to_embed), write_batch_size):
                    batch = chunks_to_embed[i : i + write_batch_size]
                    batch_embeddings = all_embeddings[i : i + len(batch)]
                    batch_data = build_chunk_rows(
                        chunks=batch,
                        embeddings=batch_embeddings,
                        document_id=document_id,
                        knowledge_base_id=kb.id,
                        tenant_id=tenant_id,
                    )
                    await chunk_repo.create_many(batch_data)

                # ===== 6. Update document statistics / 更新文档统计 =====
                doc.status = DocumentStatusEnum.COMPLETED.value
                doc.chunk_count = total_chunks
                doc.token_count = total_token_count
                doc.char_count = total_char_count
                doc.processing_completed_at = utc_now()
                doc.error_message = None
                doc.error_stage = None
                await db.commit()

                # ===== 7. Update knowledge base statistics / 更新知识库统计 =====
                await kb_repo.update_statistics(kb.id)
                await db.commit()

                # Clear Redis progress / 清除 Redis 进度
                await _clear_progress(document_id)

                # Clear retrieval cache for this knowledge base (avoid returning stale results)
                # 清除该知识库的检索缓存（避免返回过时结果）
                try:
                    from app.ai.rag.retriever import HybridRetriever

                    await HybridRetriever.invalidate_kb_cache(kb.id)
                except Exception:
                    pass

                # Socket.IO indexing complete notification / Socket.IO 索引完成通知
                try:
                    from app.services.common.notification_service import (
                        NotificationService,
                    )

                    notification_data = {
                        "document_id": document_id,
                        "kb_id": kb.id,
                        "kb_name": kb.name,
                        "doc_count": 1,
                        "document_name": doc.name,
                        "chunks": total_chunks,
                        "tokens": total_token_count,
                    }
                    payload = await NotificationService(db).build_ws_payload(
                        template_code="ai.kb_index_complete",
                        data=notification_data,
                        fallback_category="ai",
                        fallback_title=f"Document indexed: {doc.name}",
                        fallback_priority="normal",
                    )
                    if payload and tenant_id is not None:
                        from app.core.sio_bridge import notify_tenant_sync

                        notify_tenant_sync(tenant_id, payload)
                    elif payload:
                        from app.core.sio_bridge import notify_admins_sync

                        notify_admins_sync(payload)
                except Exception:
                    pass

                logger.info(
                    "Document {} processed: {} chunks, {} tokens",
                    document_id,
                    total_chunks,
                    total_token_count,
                )

                return {
                    "document_id": document_id,
                    "chunks": total_chunks,
                    "tokens": total_token_count,
                    "status": "completed",
                }

            except Exception as exc:
                logger.error(
                    "Document {} processing failed: {}",
                    document_id,
                    str(exc),
                    exc_info=True,
                )
                try:
                    error_stage = None
                    if doc.status == DocumentStatusEnum.PARSING.value:
                        error_stage = "parsing"
                    elif doc.status == DocumentStatusEnum.CHUNKING.value:
                        error_stage = "chunking"
                    elif doc.status == DocumentStatusEnum.EMBEDDING.value:
                        error_stage = "embedding"

                    doc.status = DocumentStatusEnum.ERROR.value
                    doc.error_message = str(exc)[:2000]
                    doc.error_stage = error_stage
                    doc.retry_count = (doc.retry_count or 0) + 1
                    await db.commit()

                    # Report error progress / 上报错误进度
                    await _report_progress(
                        document_id,
                        "error",
                        0,
                        tenant_id=tenant_id,
                        kb_id=kb.id if kb else None,
                    )

                    # Socket.IO indexing failed notification / Socket.IO 索引失败通知
                    try:
                        from app.services.common.notification_service import (
                            NotificationService,
                        )

                        fail_data = {
                            "document_id": document_id,
                            "kb_id": kb.id,
                            "kb_name": kb.name,
                            "doc_count": 1,
                            "document_name": doc.name,
                            "error": str(exc)[:200],
                        }
                        payload = await NotificationService(db).build_ws_payload(
                            template_code="ai.kb_index_failed",
                            data=fail_data,
                            fallback_category="ai",
                            fallback_title=f"Document indexing failed: {doc.name}",
                            fallback_priority="high",
                        )
                        if payload and tenant_id is not None:
                            from app.core.sio_bridge import notify_tenant_sync

                            notify_tenant_sync(tenant_id, payload)
                        elif payload:
                            from app.core.sio_bridge import notify_admins_sync

                            notify_admins_sync(payload)
                    except Exception:
                        pass
                except Exception:
                    pass

                return {
                    "document_id": document_id,
                    "status": "error",
                    "error": str(exc)[:500],
                }

    # Windows --pool=solo: asyncio.run() closes the event loop, causing DB connection pool to become invalid for subsequent tasks.
    # Use new_event_loop and run manually to ensure each task has a clean loop.
    # Windows --pool=solo: asyncio.run() 会关闭 event loop，导致后续任务的 DB 连接池失效。
    # 使用 new_event_loop 并手动运行，确保每次任务都有干净的 loop。
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_execute())
    finally:
        loop.close()


__all__ = ["process_document", "get_document_progress"]
