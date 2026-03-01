"""
Celery 异步文档处理任务

处理流程：解析 → 分块 → Embedding → 存储 → 更新统计
支持断点续传（从 error_stage 恢复）和 Redis 进度上报
"""

from __future__ import annotations

import asyncio

from app.core.logging import LogManager
from app.tasks.base import register_task, TenantTask
from app.core.base_model import utc_now

logger = LogManager.get_logger("ai.rag.processor")

# Redis 进度 Key 模板，TTL 1 小时
PROGRESS_KEY_TEMPLATE = "kb:doc:progress:{document_id}"
PROGRESS_TTL = 3600

# 需要 Vision 描述的图片文件类型（用户显式上传时必须描述，不受 extract_images 控制）
_IMAGE_DOC_TYPES: frozenset[str] = frozenset({"image", "jpg", "jpeg", "png", "webp", "gif"})


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
    """上报处理进度到 Redis + WS 推送"""
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

    # WS 实时推送（Celery 同步环境通过 Redis Pub/Sub 转发）
    try:
        from app.core.sio_bridge import notify_tenant_sync, notify_admins_sync
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
    """清除 Redis 进度数据"""
    try:
        from app.core.redis import cache_delete
        key = PROGRESS_KEY_TEMPLATE.format(document_id=document_id)
        await cache_delete(key)
    except Exception:
        pass


async def _load_and_parse_document(db, doc, tenant_id, kb=None) -> list:
    """
    加载并解析文档内容，返回非空 ParsedPage 列表

    统一处理 QA 类型和文件类型的文档加载逻辑，
    避免在解析/分块/嵌入阶段重复相同代码。

    当 kb.extract_images=True 时自动实例化 VisionDescriber 并注入解析器。
    空内容的 ParsedPage（content=''）会被过滤，不进入分块阶段。
    """
    from sqlalchemy import select

    from app.ai.rag.parser import get_parser, QaPairParser
    from app.enums.knowledge_base import DocumentTypeEnum
    from app.models.tenant.attachment import Attachment
    from app.storage import storage_manager
    from app.configs.service import ConfigService

    if doc.file_type == DocumentTypeEnum.QA.value:
        import json
        qa_data = json.loads(doc.metadata_extra or "{}")
        qa_parser = QaPairParser()
        return await qa_parser.parse_qa(
            question=qa_data.get("question", ""),
            answer=qa_data.get("answer", ""),
            file_name=doc.file_name,
        )

    # 按需实例化 VisionDescriber：
    # 1. kb.extract_images=True → PDF/文档中的嵌入图片也需要提取描述
    # 2. 文件类型本身是图片（用户显式上传）→ 无论 extract_images 设置，都必须描述
    _needs_vision = (
        kb is not None and getattr(kb, "extract_images", False)
    ) or doc.file_type in _IMAGE_DOC_TYPES
    vision_describer = None
    if _needs_vision:
        from app.ai.rag.vision_describer import VisionDescriber
        vision_describer = VisionDescriber(db, tenant_id)

    # 直接文本输入：content 存储在 metadata_extra 中，无 attachment
    if not doc.attachment_id and doc.metadata_extra:
        import io
        parser = get_parser(doc.file_type, vision_describer=vision_describer, knowledge_base=kb)
        pages = await parser.parse(
            io.BytesIO(doc.metadata_extra.encode("utf-8")),
            doc.file_name,
        )
        return [p for p in pages if p.content.strip()]

    if not doc.attachment_id:
        raise ValueError("Document has no attachment")

    attachment_stmt = select(Attachment).where(
        Attachment.id == doc.attachment_id,
        Attachment.is_deleted.is_(False),
    )
    att_result = await db.execute(attachment_stmt)
    attachment = att_result.scalar_one_or_none()
    if not attachment:
        raise ValueError("Attachment not found")

    config_service = ConfigService(db)
    # Resolve platform storage config (same logic as AttachmentService)
    driver_name = await config_service.get_platform_config(
        "platform_storage_driver", default="local"
    )
    if str(driver_name) == "local":
        from app.storage import LOCAL_STORAGE_ROOT
        root_path = str(LOCAL_STORAGE_ROOT)
    else:
        root_path = await config_service.get_platform_config(
            "platform_storage_root_path", default=""
        )
    base_url = await config_service.get_platform_config(
        "platform_storage_base_url", default=None
    )
    options = await config_service.get_platform_config(
        "platform_storage_options", default={}
    )
    from app.storage.base import StorageConfig
    storage_config = StorageConfig(
        driver=str(driver_name),
        root_path=str(root_path),
        base_url=base_url,
        options=options or {},
    )
    driver = storage_manager.get_driver(storage_config)
    file_content = await driver.get(attachment.path)

    parser = get_parser(doc.file_type, vision_describer=vision_describer, knowledge_base=kb)
    pages = await parser.parse(file_content, doc.file_name)
    return [p for p in pages if p.content.strip()]


async def get_document_progress(document_id: int) -> dict | None:
    """
    获取文档处理进度（供 API 调用）

    优先读 Redis，如果无数据返回 None
    """
    from app.core.redis import cache_get
    key = PROGRESS_KEY_TEMPLATE.format(document_id=document_id)
    return await cache_get(key)


@register_task(
    queue="ai_gateway",
    description="异步处理知识库文档（解析→分块→Embedding→存储）",
    max_retries=3,
    base=TenantTask,
    soft_time_limit=600,
    time_limit=660,
    acks_late=True,
)
def process_document(self: TenantTask, tenant_id: int | None, document_id: int) -> dict:
    """
    文档处理主任务（支持断点续传）

    断点续传机制：
    - error_stage='parsing' → 从解析阶段重新开始
    - error_stage='chunking' → 从分块阶段开始
    - error_stage='embedding' → 从上次成功的 chunk_index 继续

    每个阶段实时上报 Redis 进度，完成后清除。

    Args:
        tenant_id: 租户 ID
        document_id: 文档 ID

    Returns:
        处理结果摘要
    """

    async def _execute() -> dict:
        from sqlalchemy import select, func
        # 清理上一次 event loop 残留的 DB 连接（Windows --pool=solo 必需）
        from app.core.database import async_engine
        await async_engine.dispose()

        # 确保 AI 适配器已注册（Celery worker 可能未加载 celery_app.py 中的注册）
        from app.ai.adapters import AdapterRegistry
        if not AdapterRegistry.list_adapters():
            from app.ai.adapters.openai_adapter import OpenAIAdapter
            AdapterRegistry.register("openai_compatible", OpenAIAdapter)
            logger.info("Registered AI adapters in task context")

        from app.ai.gateway import AIGateway
        from app.ai.rag.chunker import get_chunker
        from app.ai.rag.parser import get_parser, QaPairParser
        from app.core.database import async_session_factory
        from app.enums.knowledge_base import DocumentStatusEnum, DocumentTypeEnum
        from app.models.ai.document_chunk import DocumentChunk
        from app.models.tenant.attachment import Attachment
        from app.repositories.ai.knowledge_base_repository import (
            DocumentChunkRepository,
            KnowledgeBaseRepository,
            KnowledgeDocumentRepository,
        )
        from app.storage import storage_manager
        from app.configs.service import ConfigService

        async with async_session_factory() as db:
            try:
                # ===== 1. 加载文档和知识库 =====
                doc_repo = KnowledgeDocumentRepository(db, tenant_id)
                doc = await doc_repo.get_by_id(document_id)
                if not doc:
                    logger.error("Document %d not found", document_id)
                    return {"error": "Document not found"}

                kb_repo = KnowledgeBaseRepository(db, tenant_id)
                kb = await kb_repo.get_by_id(doc.knowledge_base_id)
                if not kb:
                    logger.error("KnowledgeBase %d not found", doc.knowledge_base_id)
                    return {"error": "KnowledgeBase not found"}

                # 断点续传：检查 error_stage 决定起始阶段
                resume_stage = doc.error_stage  # None = 从头开始
                skip_parsing = resume_stage in ("chunking", "embedding")
                skip_chunking = resume_stage == "embedding"

                logger.info(
                    "Processing document %d (type=%s, kb=%d, resume=%s)",
                    document_id, doc.file_type, kb.id, resume_stage or "full",
                )

                # 重置错误信息
                doc.error_message = None
                doc.error_stage = None
                if not doc.processing_started_at:
                    doc.processing_started_at = utc_now()
                await db.commit()

                pages = None
                chunk_data_list = None

                # ===== 2. 解析阶段 =====
                if not skip_parsing:
                    doc.status = DocumentStatusEnum.PARSING.value
                    await db.commit()
                    await _report_progress(document_id, "parsing", 0, tenant_id=tenant_id, kb_id=kb.id)

                    pages = await _load_and_parse_document(db, doc, tenant_id, kb=kb)

                    await _report_progress(document_id, "parsing", 100, tenant_id=tenant_id, kb_id=kb.id)

                    if not pages:
                        logger.warning("Document %d parsed with 0 pages", document_id)

                # ===== 3. 分块阶段 =====
                if not skip_chunking:
                    doc.status = DocumentStatusEnum.CHUNKING.value
                    await db.commit()
                    await _report_progress(document_id, "chunking", 0, tenant_id=tenant_id, kb_id=kb.id)

                    # 如果跳过了解析（从 chunking 恢复），需要重新解析
                    if pages is None:
                        pages = await _load_and_parse_document(db, doc, tenant_id, kb=kb)

                    chunker = get_chunker(
                        strategy=kb.chunk_strategy,
                        chunk_size=kb.chunk_size,
                        chunk_overlap=kb.chunk_overlap,
                    )
                    chunk_data_list = chunker.chunk(pages or [])
                    await _report_progress(document_id, "chunking", 100, tenant_id=tenant_id, kb_id=kb.id)

                # ===== 4. Embedding 阶段（支持断点续传） =====
                doc.status = DocumentStatusEnum.EMBEDDING.value
                await db.commit()

                gateway = AIGateway(db)
                embedding_model = kb.embedding_model
                if not embedding_model:
                    raise ValueError("Embedding model not configured")
                provider = embedding_model.provider
                if not provider:
                    raise ValueError("Embedding model provider not found")

                # 断点续传：如果从 embedding 阶段恢复，查询已有分块数
                existing_chunk_count = 0
                if skip_chunking:
                    # 需要重新生成 chunk_data_list（从 embedding 恢复）
                    if chunk_data_list is None:
                        # 重新解析+分块（跳过 embedding 阶段已完成的部分）
                        pages = await _load_and_parse_document(db, doc, tenant_id, kb=kb)

                        chunker = get_chunker(
                            strategy=kb.chunk_strategy,
                            chunk_size=kb.chunk_size,
                            chunk_overlap=kb.chunk_overlap,
                        )
                        chunk_data_list = chunker.chunk(pages or [])

                    # 查询已成功写入的分块数（用于断点续传）
                    count_stmt = (
                        select(func.count(DocumentChunk.id))
                        .where(
                            DocumentChunk.document_id == document_id,
                            DocumentChunk.knowledge_base_id == kb.id,
                            DocumentChunk.is_deleted.is_(False),
                            DocumentChunk.embedding.isnot(None),
                        )
                    )
                    count_result = await db.execute(count_stmt)
                    existing_chunk_count = count_result.scalar() or 0
                    logger.info(
                        "Resuming embedding from chunk %d/%d for doc %d",
                        existing_chunk_count, len(chunk_data_list), document_id,
                    )

                if chunk_data_list is None:
                    chunk_data_list = []

                total_chunks = len(chunk_data_list)
                total_char_count = sum(c.char_count for c in chunk_data_list)

                # 从断点位置开始 Embedding
                chunks_to_embed = chunk_data_list[existing_chunk_count:]
                # 从供应商配置读取 embedding_batch_size，默认 10（DashScope 限制）
                embedding_batch_size = 10
                if provider.config and isinstance(provider.config, dict):
                    embedding_batch_size = provider.config.get("embedding_batch_size", 10)
                batch_size = min(embedding_batch_size, len(chunks_to_embed) or 1)
                all_embeddings: list[list[float]] = []
                total_token_count = 0
                processed_so_far = existing_chunk_count

                await _report_progress(
                    document_id, "embedding", 
                    int(processed_so_far / max(total_chunks, 1) * 100),
                    total_chunks, processed_so_far,
                    tenant_id=tenant_id, kb_id=kb.id,
                )

                from app.ai.rag.text_cleaner import clean_for_embedding

                for i in range(0, len(chunks_to_embed), batch_size):
                    batch = chunks_to_embed[i:i + batch_size]
                    texts = [clean_for_embedding(c.content) for c in batch]

                    response = await gateway.embedding(
                        provider_code=provider.code,
                        texts=texts,
                        model=embedding_model.code,
                        tenant_id=tenant_id,
                    )

                    all_embeddings.extend(response.embeddings)
                    total_token_count += response.total_tokens or 0
                    processed_so_far += len(batch)

                    # 上报进度
                    await _report_progress(
                        document_id, "embedding",
                        int(processed_so_far / max(total_chunks, 1) * 100),
                        total_chunks, processed_so_far,
                        tenant_id=tenant_id, kb_id=kb.id,
                    )

                    logger.info(
                        "Embedding %d/%d for doc %d",
                        processed_so_far, total_chunks, document_id,
                    )

                # ===== 5. 批量写入 document_chunks =====
                chunk_repo = DocumentChunkRepository(db, tenant_id)

                if existing_chunk_count == 0:
                    # 全新处理：先删除旧分块
                    await chunk_repo.delete_by_document(document_id, soft=False)

                # 只写入新生成的分块
                write_batch_size = 500
                for i in range(0, len(chunks_to_embed), write_batch_size):
                    batch = chunks_to_embed[i:i + write_batch_size]
                    batch_data = []
                    for idx, cd in enumerate(batch):
                        embedding_vec = (
                            all_embeddings[idx + i]  # all_embeddings 从0开始对应 chunks_to_embed
                            if (idx + i) < len(all_embeddings)
                            else None
                        )
                        batch_data.append({
                            "document_id": document_id,
                            "knowledge_base_id": kb.id,
                            "chunk_index": cd.chunk_index,
                            "content": cd.content,
                            "content_hash": cd.content_hash,
                            "char_count": cd.char_count,
                            "token_count": 0,
                            "embedding": embedding_vec,
                            "metadata_": cd.metadata,
                            "tenant_id": tenant_id,
                        })
                    await chunk_repo.create_many(batch_data)

                # ===== 6. 更新文档统计 =====
                doc.status = DocumentStatusEnum.COMPLETED.value
                doc.chunk_count = total_chunks
                doc.token_count = total_token_count
                doc.char_count = total_char_count
                doc.processing_completed_at = utc_now()
                doc.error_message = None
                doc.error_stage = None
                await db.commit()

                # ===== 7. 更新知识库统计 =====
                await kb_repo.update_statistics(kb.id)
                await db.commit()

                # 清除 Redis 进度
                await _clear_progress(document_id)

                # 清除该知识库的检索缓存（避免返回过时结果）
                try:
                    from app.ai.rag.retriever import HybridRetriever
                    await HybridRetriever.invalidate_kb_cache(kb.id)
                except Exception:
                    pass

                # Socket.IO 索引完成通知
                try:
                    notification = {
                        "type": "ai.kb_index_complete",
                        "category": "ai",
                        "title": f"Document indexed: {doc.name}",
                        "data": {
                            "document_id": document_id,
                            "kb_id": kb.id,
                            "chunks": total_chunks,
                            "tokens": total_token_count,
                        },
                        "priority": "normal",
                    }
                    if tenant_id is not None:
                        from app.core.sio_bridge import notify_tenant_sync
                        notify_tenant_sync(tenant_id, notification)
                    else:
                        from app.core.sio_bridge import notify_admins_sync
                        notify_admins_sync(notification)
                except Exception:
                    pass

                logger.info(
                    "Document %d processed: %d chunks, %d tokens",
                    document_id, total_chunks, total_token_count,
                )

                return {
                    "document_id": document_id,
                    "chunks": total_chunks,
                    "tokens": total_token_count,
                    "status": "completed",
                }

            except Exception as exc:
                logger.error(
                    "Document %d processing failed: %s",
                    document_id, str(exc),
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

                    # 上报错误进度
                    await _report_progress(
                        document_id, "error", 0,
                        tenant_id=tenant_id, kb_id=kb.id if kb else None,
                    )

                    # Socket.IO 索引失败通知
                    try:
                        fail_notification = {
                            "type": "ai.kb_index_failed",
                            "category": "ai",
                            "title": f"Document indexing failed: {doc.name}",
                            "data": {
                                "document_id": document_id,
                                "kb_id": kb.id,
                                "error": str(exc)[:200],
                            },
                            "priority": "high",
                        }
                        if tenant_id is not None:
                            from app.core.sio_bridge import notify_tenant_sync
                            notify_tenant_sync(tenant_id, fail_notification)
                        else:
                            from app.core.sio_bridge import notify_admins_sync
                            notify_admins_sync(fail_notification)
                    except Exception:
                        pass
                except Exception:
                    pass

                return {
                    "document_id": document_id,
                    "status": "error",
                    "error": str(exc)[:500],
                }

    # Windows --pool=solo: asyncio.run() 会关闭 event loop，导致后续任务的 DB 连接池失效。
    # 使用 new_event_loop 并手动运行，确保每次任务都有干净的 loop。
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_execute())
    finally:
        loop.close()


__all__ = ["process_document", "get_document_progress"]
