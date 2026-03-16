"""
企业端知识库管理 API / Tenant Knowledge Base Management API

提供知识库 CRUD、文档管理、检索测试等接口
Provides knowledge base CRUD, document management, search testing endpoints
"""

import hashlib
import os

from fastapi import File, Form, Request, UploadFile

from app.core.base_controller import TenantController
from app.core.deps import ActiveTenantAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.recycle_bin import register_tenant_recycle_bin_routes
from app.core.response import created, deleted, paginated, success
from app.enums.knowledge_base import DocumentStatusEnum, DocumentTypeEnum
from app.enums.rbac import PermissionScope
from app.exceptions import BusinessException, NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.schemas.ai.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseSearchRequest,
    KnowledgeBaseUpdate,
    QAPairCreate,
    TextDocumentCreate,
)
from app.schemas.common.query import FilterOp, FilterRule
from app.services.ai.knowledge_base_service import (
    DocumentChunkService,
    KnowledgeBaseService,
    KnowledgeDocumentService,
)


async def _ensure_tenant_owned_kb(
    db,
    tenant_id: int,
    kb_id: int,
):
    """
    确保知识库为企业自有（tenant_id 与当前企业匹配）才允许变更操作 / Ensure KB is tenant-owned before mutations.

    平台创建的全局 KB（tenant_id=null）及其他企业的 KB 对当前企业只读，
    不允许上传文档、删除文档等变更操作。
    Platform-created global KBs (tenant_id=null) and other tenants' KBs are read-only,
    upload/delete document mutations are not allowed.
    """
    kb_service = KnowledgeBaseService(db, tenant_id)
    kb = await kb_service.get_by_id(kb_id)
    if not kb:
        raise NotFoundException(message=_("knowledge_base.error.not_found"))
    if kb.tenant_id != tenant_id:
        raise BusinessException(message=_("knowledge_base.error.readonly"))
    return kb


# 支持的文件类型映射 / Supported file type mapping
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


@permission_resource(
    resource="knowledge_base",
    name="menu.tenant.knowledge_base",
    scope=PermissionScope.ALL_TENANTS,
    parent_resource="ai_workspace",
    menu=MenuConfig(
        icon="lucide:book-open",
        path="/ai/knowledge-bases",
        component="ai/knowledge-bases/index",
        parent="ai_workspace",
        sort_order=30,
    ),
)
class TenantKnowledgeBaseController(TenantController):
    """
    企业知识库管理控制器 / Tenant Knowledge Base Management Controller

    提供知识库 CRUD、文档上传/管理、检索测试
    Provides knowledge base CRUD, document upload/management, search testing
    """

    prefix = "/ai/knowledge-bases"
    tags = [_("menu.tags.tenant_knowledge_base")]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        # 回收站路由必须在 /{id} 之前注册，避免路径冲突 / Recycle bin routes must be registered before /{id} to avoid path conflicts
        register_tenant_recycle_bin_routes(
            router=router,
            service_class=KnowledgeBaseService,
            resource_name="knowledge_base",
        )

        # ========================================
        # 知识库 CRUD / Knowledge Base CRUD
        # ========================================

        @router.get("/selectable", summary="获取可 @ 选择的知识库列表")
        @action_read("action.knowledge_base.selectable")
        async def list_selectable_knowledge_bases(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取企业端可 @ 选择的知识库列表 / Get tenant selectable knowledge base list

            返回 scope=tenant(本企业) + scope=global 的知识库（精简字段）
            Returns scope=tenant (current tenant) + scope=global knowledge bases (compact fields)

            权限 / Permission: knowledge_base:selectable
            """
            from sqlalchemy import and_, or_, select

            from app.enums.common import ResourceScopeEnum
            from app.models.ai.knowledge_base import KnowledgeBase
            from app.repositories.system.resource_tenant_assignment_repository import (
                assigned_resource_ids_subquery,
            )

            tenant_id = tenant_admin.tenant_id
            assigned_subq = assigned_resource_ids_subquery("knowledge_base", tenant_id)
            stmt = (
                select(KnowledgeBase)
                .where(
                    KnowledgeBase.is_deleted.is_(False),
                    or_(
                        # 本企业创建的 KB / KBs created by current tenant
                        and_(
                            KnowledgeBase.scope == ResourceScopeEnum.ALL_TENANTS.value,
                            KnowledgeBase.tenant_id == tenant_id,
                        ),
                        # 全局共享的 KB（admin 创建，所有企业可见） / Global shared KBs (admin-created, visible to all tenants)
                        KnowledgeBase.scope == ResourceScopeEnum.ADMIN_AND_ALL.value,
                        # 已分配给当前企业的 KB / KBs assigned to current tenant
                        and_(
                            KnowledgeBase.scope.in_([
                                ResourceScopeEnum.ASSIGNED_TENANTS.value,
                                ResourceScopeEnum.ADMIN_AND_ASSIGNED.value,
                            ]),
                            KnowledgeBase.id.in_(assigned_subq),
                        ),
                    ),
                )
                .order_by(KnowledgeBase.name.asc())
            )
            result = await db.execute(stmt)
            kbs = list(result.scalars().all())

            items = [
                {
                    "id": kb.id,
                    "name": kb.name,
                    "description": kb.description,
                    "scope": kb.scope,
                    "document_count": kb.document_count,
                }
                for kb in kbs
            ]
            return success(data=items)

        @router.get("", summary="获取知识库列表")
        @action_read("action.knowledge_base.list")
        async def list_knowledge_bases(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            query: QueryParams,
        ):
            """
            获取知识库列表 / Get knowledge base list

            支持 JSON:API 分页、筛选、排序
            Supports JSON:API pagination, filtering, sorting
            权限 / Permission: knowledge_base:list
            """
            service = KnowledgeBaseService(db, tenant_admin.tenant_id)
            items, total = await service.query_list(spec=query)

            from app.api.shared._kb_helpers import enrich_model_names

            result = []
            for kb in items:
                item = kb.to_dict()
                enrich_model_names(kb, item)
                result.append(item)

            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get("/{kb_id}", summary="获取知识库详情")
        @action_read("action.knowledge_base.detail")
        async def get_knowledge_base(
            request: Request,
            db: DbSession,
            kb_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取知识库详情 / Get knowledge base details

            权限 / Permission: knowledge_base:detail
            """
            service = KnowledgeBaseService(db, tenant_admin.tenant_id)
            result = await service.get_kb_detail(kb_id)

            return success(data=result)

        @router.post("", summary="创建知识库")
        @action_create("action.knowledge_base.create")
        async def create_knowledge_base(
            request: Request,
            db: DbSession,
            data: KnowledgeBaseCreate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            创建知识库 / Create knowledge base

            权限 / Permission: knowledge_base:create
            """
            service = KnowledgeBaseService(db, tenant_admin.tenant_id)
            kb = await service.create(data.model_dump(exclude_unset=True))
            await db.commit()

            from app.api.shared._kb_helpers import enrich_model_names

            result = kb.to_dict()
            enrich_model_names(kb, result)
            return created(
                data=result,
                message=_("knowledge_base.created"),
            )

        @router.put("/{kb_id}", summary="更新知识库")
        @action_update("action.knowledge_base.update")
        async def update_knowledge_base(
            request: Request,
            db: DbSession,
            kb_id: int,
            data: KnowledgeBaseUpdate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            更新知识库配置 / Update knowledge base configuration

            权限 / Permission: knowledge_base:update
            """
            service = KnowledgeBaseService(db, tenant_admin.tenant_id)

            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            updated = await service.update(
                kb_id, data.model_dump(exclude_unset=True),
            )
            await db.commit()

            from app.api.shared._kb_helpers import enrich_model_names

            result = updated.to_dict()
            enrich_model_names(updated, result)
            return success(
                data=result,
                message=_("knowledge_base.updated"),
            )

        @router.delete("/{kb_id}", summary="删除知识库")
        @action_delete("action.knowledge_base.delete")
        async def delete_knowledge_base(
            request: Request,
            db: DbSession,
            kb_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            删除知识库（软删除，级联删除文档和分块） / Delete knowledge base (soft delete, cascades to documents and chunks)

            权限 / Permission: knowledge_base:delete
            """
            service = KnowledgeBaseService(db, tenant_admin.tenant_id)

            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            await service.delete(kb_id)
            await db.commit()

            return deleted(message=_("knowledge_base.deleted"))

        # ========================================
        # 文档管理 / Document Management
        # ========================================

        @router.get("/{kb_id}/documents", summary="获取文档列表")
        @action_read("action.knowledge_base.document_list")
        async def list_documents(
            request: Request,
            db: DbSession,
            kb_id: int,
            tenant_admin: ActiveTenantAdmin,
            query: QueryParams,
        ):
            """
            获取知识库下的文档列表 / Get document list under knowledge base

            权限 / Permission: knowledge_base:document_list
            """
            # 验证知识库存在 / Verify knowledge base exists
            kb_service = KnowledgeBaseService(db, tenant_admin.tenant_id)
            kb = await kb_service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            doc_service = KnowledgeDocumentService(db, tenant_admin.tenant_id)

            # 添加知识库 ID 过滤 / Add knowledge base ID filter
            query.filters.append(FilterRule(
                field="knowledge_base_id", op=FilterOp.eq, value=str(kb_id)
            ))

            items, total = await doc_service.query_list(spec=query)
            result = [doc.to_dict() for doc in items]

            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.post("/{kb_id}/documents/upload", summary="上传文档")
        @action_create("action.knowledge_base.document_upload")
        async def upload_document(
            request: Request,
            db: DbSession,
            kb_id: int,
            tenant_admin: ActiveTenantAdmin,
            file: UploadFile = File(..., description="上传的文档文件"),
        ):
            """
            上传文档到知识库 / Upload document to knowledge base

            复用附件系统存储文件，创建文档记录并触发 Celery 异步处理。
            Reuses attachment system for file storage, creates document record and triggers Celery async processing.

            支持格式 / Supported formats: txt, md, pdf, docx, csv, html
            权限 / Permission: knowledge_base:document_upload
            """
            from app.enums.attachment import AttachmentSource, AttachmentVisibility
            from app.services.tenant.attachment_service import AttachmentService

            # 验证知识库存在且为企业自有 / Verify KB exists and is tenant-owned
            await _ensure_tenant_owned_kb(db, tenant_admin.tenant_id, kb_id)

            # 配额检查 / Quota check
            kb_service = KnowledgeBaseService(db, tenant_admin.tenant_id)
            await kb_service.check_document_quota(kb_id)

            # 验证文件类型 / Validate file type
            filename = file.filename or "unnamed"
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise BusinessException(
                    message=_("knowledge_base.error.unsupported_file_type"),
                )

            file_type = ALLOWED_EXTENSIONS[ext]

            # 读取文件内容并计算哈希 / Read file content and calculate hash
            file_bytes = await file.read()
            file_hash = hashlib.md5(file_bytes).hexdigest()
            file_size = len(file_bytes)

            # 去重检查 / Deduplication check
            doc_service = KnowledgeDocumentService(db, tenant_admin.tenant_id)
            existing = await doc_service.get_by_kb_and_hash(kb_id, file_hash)
            if existing:
                raise BusinessException(
                    message=_("knowledge_base.error.document_exists"),
                )

            # 复用附件系统上传 / Reuse attachment system for upload
            import io
            attachment_service = AttachmentService(db, tenant_admin.tenant_id)
            upload_result = await attachment_service.upload_file(
                content=io.BytesIO(file_bytes),
                filename=filename,
                file_size=file_size,
                mime_type=file.content_type,
                visibility=AttachmentVisibility.PRIVATE,
                source=AttachmentSource.TENANT_ADMIN,
                uploader_id=tenant_admin.id,
                business_type="knowledge_document",
                business_id=kb_id,
            )

            attachment = upload_result["attachment"]

            # 创建文档记录 / Create document record
            doc = await doc_service.create({
                "knowledge_base_id": kb_id,
                "attachment_id": attachment.id,
                "file_name": filename,
                "file_type": file_type,
                "file_size": file_size,
                "file_hash": file_hash,
                "status": DocumentStatusEnum.PENDING.value,
            })
            await db.commit()

            # 触发 Celery 异步处理 / Trigger Celery async processing
            from app.ai.rag.processor import process_document
            process_document.delay(
                tenant_id=tenant_admin.tenant_id,
                document_id=doc.id,
            )

            return created(
                data=doc.to_dict(),
                message=_("knowledge_base.document.uploaded"),
            )

        @router.get("/{kb_id}/documents/{doc_id}", summary="获取文档详情")
        @action_read("action.knowledge_base.document_detail")
        async def get_document(
            request: Request,
            db: DbSession,
            kb_id: int,
            doc_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取文档详情 / Get document details

            权限 / Permission: knowledge_base:document_detail
            """
            doc_service = KnowledgeDocumentService(db, tenant_admin.tenant_id)
            doc = await doc_service.get_by_id(doc_id)

            if not doc or doc.knowledge_base_id != kb_id:
                raise NotFoundException(
                    message=_("knowledge_base.error.document_not_found"),
                )

            return success(data=doc.to_dict())

        @router.post("/{kb_id}/documents/text", summary="直接文本输入")
        @action_create("action.knowledge_base.document_text")
        async def create_text_document(
            request: Request,
            db: DbSession,
            kb_id: int,
            data: TextDocumentCreate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            直接输入文本内容创建文档 / Create document from direct text input

            将文本包装为虚拟 TXT 文件，走标准分块/Embedding 流程
            Wraps text as virtual TXT file, follows standard chunking/embedding pipeline
            权限 / Permission: knowledge_base:document_text
            """
            import hashlib

            await _ensure_tenant_owned_kb(db, tenant_admin.tenant_id, kb_id)

            kb_service = KnowledgeBaseService(db, tenant_admin.tenant_id)
            await kb_service.check_document_quota(kb_id)

            content_bytes = data.content.encode("utf-8")
            content_hash = hashlib.md5(content_bytes).hexdigest()

            doc_service = KnowledgeDocumentService(db, tenant_admin.tenant_id)
            existing = await doc_service.get_by_kb_and_hash(kb_id, content_hash)
            if existing:
                raise BusinessException(
                    message=_("knowledge_base.document.error.duplicate"),
                )

            safe_title = data.title.replace("/", "_").replace("\\", "_")
            doc = await doc_service.create({
                "knowledge_base_id": kb_id,
                "file_name": f"{safe_title}.txt",
                "file_type": DocumentTypeEnum.TXT.value,
                "file_size": len(content_bytes),
                "file_hash": content_hash,
                "status": DocumentStatusEnum.PENDING.value,
                "metadata_extra": data.content,
            })
            await db.commit()

            from app.ai.rag.processor import process_document
            process_document.delay(
                tenant_id=tenant_admin.tenant_id,
                document_id=doc.id,
            )

            return created(
                data=doc.to_dict(),
                message=_("knowledge_base.document.uploaded"),
            )

        @router.get("/{kb_id}/documents/{doc_id}/chunks", summary="文档分块预览")
        @action_read("action.knowledge_base.document_chunks")
        async def get_document_chunks(
            request: Request,
            db: DbSession,
            kb_id: int,
            doc_id: int,
            tenant_admin: ActiveTenantAdmin,
            page: int = 1,
            page_size: int = 20,
        ):
            """
            获取文档的分块列表（预览用） / Get document chunk list (for preview)

            权限 / Permission: knowledge_base:document_chunks
            """
            doc_service = KnowledgeDocumentService(db, tenant_admin.tenant_id)
            doc = await doc_service.get_by_id(doc_id)
            if not doc or doc.knowledge_base_id != kb_id:
                raise NotFoundException(
                    message=_("knowledge_base.error.document_not_found"),
                )

            chunk_service = DocumentChunkService(db, tenant_admin.tenant_id)
            chunks = await chunk_service.repo.get_by_document(
                document_id=doc_id,
                skip=(page - 1) * page_size,
                limit=page_size,
            )

            return success(data={
                "chunks": [
                    {
                        "id": c.id,
                        "chunk_index": c.chunk_index,
                        "content": c.content,
                        "char_count": c.char_count,
                        "token_count": c.token_count,
                        "metadata": c.metadata_,
                    }
                    for c in chunks
                ],
                "total": doc.chunk_count or 0,
            })

        @router.delete("/{kb_id}/documents/{doc_id}", summary="删除文档")
        @action_delete("action.knowledge_base.document_delete")
        async def delete_document(
            request: Request,
            db: DbSession,
            kb_id: int,
            doc_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            删除文档（级联删除分块） / Delete document (cascades to chunks)

            权限 / Permission: knowledge_base:document_delete
            """
            await _ensure_tenant_owned_kb(db, tenant_admin.tenant_id, kb_id)

            doc_service = KnowledgeDocumentService(db, tenant_admin.tenant_id)
            doc = await doc_service.get_by_id(doc_id)

            if not doc or doc.knowledge_base_id != kb_id:
                raise NotFoundException(
                    message=_("knowledge_base.error.document_not_found"),
                )

            # 删除分块 / Delete chunks
            chunk_service = DocumentChunkService(db, tenant_admin.tenant_id)
            await chunk_service.delete_by_document(doc_id)

            # 删除文档 / Delete document
            await doc_service.delete(doc_id)

            # 更新知识库统计 / Update knowledge base statistics
            kb_service = KnowledgeBaseService(db, tenant_admin.tenant_id)
            await kb_service.update_statistics(kb_id)
            await db.commit()

            from app.ai.rag.retriever import HybridRetriever
            await HybridRetriever.invalidate_kb_cache(kb_id)

            return deleted(message=_("knowledge_base.document.deleted"))

        @router.post(
            "/{kb_id}/documents/{doc_id}/retry",
            summary="重试失败文档",
        )
        @action_update("action.knowledge_base.document_retry")
        async def retry_document(
            request: Request,
            db: DbSession,
            kb_id: int,
            doc_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            重试失败的文档处理（断点续传） / Retry failed document processing (resume from checkpoint)

            权限 / Permission: knowledge_base:document_retry
            """
            await _ensure_tenant_owned_kb(db, tenant_admin.tenant_id, kb_id)

            doc_service = KnowledgeDocumentService(db, tenant_admin.tenant_id)
            doc = await doc_service.get_by_id(doc_id)

            if not doc or doc.knowledge_base_id != kb_id:
                raise NotFoundException(
                    message=_("knowledge_base.error.document_not_found"),
                )

            if doc.status != DocumentStatusEnum.ERROR.value:
                raise BusinessException(
                    message=_("knowledge_base.error.document_not_error"),
                )

            # 重置为 pending 保留 error_stage（供断点续传） / Reset to pending, keep error_stage (for resume)
            doc.status = DocumentStatusEnum.PENDING.value
            await db.commit()

            # 触发 Celery 重新处理 / Trigger Celery reprocessing
            from app.ai.rag.processor import process_document
            process_document.delay(
                tenant_id=tenant_admin.tenant_id,
                document_id=doc.id,
            )

            return success(
                data=doc.to_dict(),
                message=_("knowledge_base.document.retrying"),
            )

        @router.get(
            "/{kb_id}/documents/{doc_id}/progress",
            summary="获取文档处理进度",
        )
        @action_read("action.knowledge_base.document_progress")
        async def get_document_progress(
            request: Request,
            db: DbSession,
            kb_id: int,
            doc_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取文档实时处理进度（Redis） / Get real-time document processing progress (Redis)

            权限 / Permission: knowledge_base:document_progress
            """
            from app.ai.rag.processor import get_document_progress as _get_progress

            doc_service = KnowledgeDocumentService(db, tenant_admin.tenant_id)
            doc = await doc_service.get_by_id(doc_id)

            if not doc or doc.knowledge_base_id != kb_id:
                raise NotFoundException(
                    message=_("knowledge_base.error.document_not_found"),
                )

            # 从 Redis 获取实时进度 / Get real-time progress from Redis
            progress = await _get_progress(doc_id)
            if progress is None:
                # 回退到数据库状态 / Fallback to database status
                progress = {
                    "stage": doc.status,
                    "progress": 100 if doc.status == "completed" else 0,
                    "total_chunks": doc.chunk_count,
                    "processed_chunks": doc.chunk_count if doc.status == "completed" else 0,
                }

            return success(data=progress)

        # ========================================
        # 重索引 / Re-index
        # ========================================

        @router.post("/{kb_id}/reindex", summary="重新向量化知识库")
        @action_update("action.knowledge_base.reindex")
        async def reindex_knowledge_base(
            request: Request,
            db: DbSession,
            kb_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            重新向量化知识库所有文档 / Re-vectorize all knowledge base documents

            删除现有分块并重新触发处理 / Deletes existing chunks and re-triggers processing
            权限 / Permission: knowledge_base:reindex
            """
            await _ensure_tenant_owned_kb(db, tenant_admin.tenant_id, kb_id)

            kb_service = KnowledgeBaseService(db, tenant_admin.tenant_id)
            count = await kb_service.reindex_knowledge_base(kb_id)

            from app.ai.rag.retriever import HybridRetriever
            await HybridRetriever.invalidate_kb_cache(kb_id)

            return success(
                data={"document_count": count},
                message=_("knowledge_base.reindex_started"),
            )

        # ========================================
        # Q&A 问答对 / Q&A Pairs
        # ========================================

        @router.post("/{kb_id}/qa-pairs", summary="添加 Q&A 问答对")
        @action_create("action.knowledge_base.qa_create")
        async def create_qa_pair(
            request: Request,
            db: DbSession,
            kb_id: int,
            data: QAPairCreate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            手动添加 Q&A 问答对 / Manually add Q&A pair

            直接创建文档记录并生成对应 chunk，无需上传文件
            Directly creates document record and generates corresponding chunk, no file upload needed
            权限 / Permission: knowledge_base:qa_create
            """
            import hashlib

            kb = await _ensure_tenant_owned_kb(db, tenant_admin.tenant_id, kb_id)

            # 配额检查 / Quota check
            kb_service = KnowledgeBaseService(db, tenant_admin.tenant_id)
            await kb_service.check_document_quota(kb_id)

            # 构建 Q&A 内容 / Build Q&A content
            qa_content = f"Q: {data.question}\nA: {data.answer}"
            content_hash = hashlib.md5(qa_content.encode("utf-8")).hexdigest()

            # 去重检查 / Deduplication check
            doc_service = KnowledgeDocumentService(db, tenant_admin.tenant_id)
            existing = await doc_service.get_by_kb_and_hash(kb_id, content_hash)
            if existing:
                raise BusinessException(
                    message=_("knowledge_base.document.error.duplicate"),
                )

            # 创建文档记录（metadata_extra 存储原始 Q&A JSON，供 reindex 使用）
            # Create document record (metadata_extra stores original Q&A JSON for reindex)
            import json as _json
            doc = await doc_service.create({
                "knowledge_base_id": kb_id,
                "file_name": f"qa_{content_hash[:8]}.txt",
                "file_type": DocumentTypeEnum.QA.value,
                "file_size": len(qa_content.encode("utf-8")),
                "file_hash": content_hash,
                "status": DocumentStatusEnum.COMPLETED.value,
                "chunk_count": 1,
                "char_count": len(qa_content),
                "metadata_extra": _json.dumps({"question": data.question, "answer": data.answer}),
            })

            # 直接创建 chunk（无需 Celery 异步） / Directly create chunk (no Celery async needed)
            from app.ai.rag.embedding import EmbeddingService
            from app.ai.utils.token_estimator import estimate_tokens

            chunk_service = DocumentChunkService(db, tenant_admin.tenant_id)

            # 生成 embedding / Generate embedding
            embedding_service = EmbeddingService(db, tenant_admin.tenant_id)
            embeddings = await embedding_service.generate_embedding(qa_content, kb)

            token_count = estimate_tokens(qa_content)

            await chunk_service.create({
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
                    "question": data.question,
                    "answer": data.answer,
                },
            })

            # 更新文档 token_count / Update document token_count
            doc.token_count = token_count

            # 更新知识库统计 / Update knowledge base statistics
            await kb_service.update_statistics(kb_id)
            await db.commit()

            from app.ai.rag.retriever import HybridRetriever
            await HybridRetriever.invalidate_kb_cache(kb_id)

            return created(
                data=doc.to_dict(),
                message=_("knowledge_base.document.uploaded"),
            )

        @router.post("/{kb_id}/qa-pairs/batch", summary="批量导入 Q&A 问答对")
        @action_create("action.knowledge_base.qa_batch")
        async def batch_import_qa(
            request: Request,
            db: DbSession,
            kb_id: int,
            tenant_admin: ActiveTenantAdmin,
            file: UploadFile = File(..., description="CSV/Excel 文件（需含 question, answer 列）"),
        ):
            """
            批量导入 Q&A 问答对（CSV/Excel） / Batch import Q&A pairs (CSV/Excel)

            文件需包含 question 和 answer 两列，每行创建一条 Q&A 文档+chunk。
            File must contain question and answer columns, each row creates one Q&A document+chunk.
            跳过空行和重复行，返回导入统计。
            Skips empty and duplicate rows, returns import statistics.
            权限 / Permission: knowledge_base:qa_batch
            """
            import hashlib
            import os

            kb = await _ensure_tenant_owned_kb(db, tenant_admin.tenant_id, kb_id)

            # 配额检查 / Quota check
            kb_service = KnowledgeBaseService(db, tenant_admin.tenant_id)
            await kb_service.check_document_quota(kb_id)

            filename = file.filename or "unnamed"
            ext = os.path.splitext(filename)[1].lower()
            if ext not in (".csv", ".xlsx"):
                raise BusinessException(
                    message=_("knowledge_base.error.unsupported_file_type"),
                )

            file_bytes = await file.read()
            import io

            import pandas as pd

            if ext == ".csv":
                df = pd.read_csv(io.BytesIO(file_bytes), dtype=str)
            else:
                df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)

            if "question" not in df.columns or "answer" not in df.columns:
                raise BusinessException(
                    message=_("knowledge_base.qa.batch.missing_columns"),
                )

            from app.ai.rag.embedding import EmbeddingService
            from app.ai.utils.token_estimator import estimate_tokens

            doc_service = KnowledgeDocumentService(db, tenant_admin.tenant_id)
            chunk_service = DocumentChunkService(db, tenant_admin.tenant_id)
            embedding_service = EmbeddingService(db, tenant_admin.tenant_id)

            imported = 0
            skipped = 0
            errors: list[str] = []

            for row_idx, row in df.iterrows():
                q = str(row.get("question", "")).strip()
                a = str(row.get("answer", "")).strip()
                if not q or not a or q == "nan" or a == "nan":
                    skipped += 1
                    continue

                qa_content = f"Q: {q}\nA: {a}"
                content_hash = hashlib.md5(qa_content.encode("utf-8")).hexdigest()

                existing = await doc_service.get_by_kb_and_hash(kb_id, content_hash)
                if existing:
                    skipped += 1
                    continue

                try:
                    import json as _json
                    doc = await doc_service.create({
                        "knowledge_base_id": kb_id,
                        "file_name": f"qa_{content_hash[:8]}.txt",
                        "file_type": DocumentTypeEnum.QA.value,
                        "file_size": len(qa_content.encode("utf-8")),
                        "file_hash": content_hash,
                        "status": DocumentStatusEnum.COMPLETED.value,
                        "chunk_count": 1,
                        "char_count": len(qa_content),
                        "metadata_extra": _json.dumps({"question": q, "answer": a}),
                    })

                    embeddings = await embedding_service.generate_embedding(qa_content, kb)
                    token_count = estimate_tokens(qa_content)

                    await chunk_service.create({
                        "document_id": doc.id,
                        "knowledge_base_id": kb_id,
                        "chunk_index": 0,
                        "content": qa_content,
                        "content_hash": content_hash,
                        "embedding": embeddings,
                        "char_count": len(qa_content),
                        "token_count": token_count,
                        "metadata_": {"type": "qa", "question": q, "answer": a},
                    })
                    doc.token_count = token_count
                    imported += 1
                except Exception as exc:
                    errors.append(f"Row {int(row_idx) + 2}: {str(exc)[:100]}")

            await kb_service.update_statistics(kb_id)
            await db.commit()

            from app.ai.rag.retriever import HybridRetriever
            await HybridRetriever.invalidate_kb_cache(kb_id)

            return success(data={
                "imported": imported,
                "skipped": skipped,
                "errors": errors[:20],
            })

        # ========================================
        # URL 网页导入 / URL Web Page Import
        # ========================================

        @router.post("/{kb_id}/documents/url", summary="URL 网页导入")
        @action_create("action.knowledge_base.document_url")
        async def import_from_url(
            request: Request,
            db: DbSession,
            kb_id: int,
            tenant_admin: ActiveTenantAdmin,
            urls: list[str] = Form(..., description="URL 列表"),
        ):
            """
            通过 URL 导入网页内容 / Import web page content via URL

            每个 URL 创建一个文档，异步爬取和处理。
            Each URL creates one document, crawled and processed asynchronously.
            权限 / Permission: knowledge_base:document_url
            """
            await _ensure_tenant_owned_kb(db, tenant_admin.tenant_id, kb_id)

            # 配额检查 / Quota check
            kb_service = KnowledgeBaseService(db, tenant_admin.tenant_id)
            await kb_service.check_document_quota(kb_id)

            doc_service = KnowledgeDocumentService(db, tenant_admin.tenant_id)
            created_docs: list[dict] = []

            for url in urls:
                url = url.strip()
                if not url or not url.startswith(("http://", "https://")):
                    continue

                url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
                existing = await doc_service.get_by_kb_and_hash(kb_id, url_hash)
                if existing:
                    continue

                doc = await doc_service.create({
                    "knowledge_base_id": kb_id,
                    "file_name": url[:200],
                    "file_type": DocumentTypeEnum.URL.value,
                    "file_size": len(url.encode("utf-8")),
                    "file_hash": url_hash,
                    "source_url": url,
                    "status": DocumentStatusEnum.PENDING.value,
                    "metadata_extra": url,
                })
                created_docs.append(doc.to_dict())

            await db.commit()

            from app.ai.rag.processor import process_document
            for doc_dict in created_docs:
                process_document.delay(
                    tenant_id=tenant_admin.tenant_id,
                    document_id=doc_dict["id"],
                )

            return success(data={
                "created": len(created_docs),
                "documents": created_docs,
            })

        # ========================================
        # 检索测试 / Search Testing
        # ========================================

        @router.post("/{kb_id}/search", summary="检索测试")
        @action_read("action.knowledge_base.search")
        async def search_knowledge_base(
            request: Request,
            db: DbSession,
            kb_id: int,
            data: KnowledgeBaseSearchRequest,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            知识库检索测试 / Knowledge base search testing

            输入查询文本，返回最相似的分块列表
            Input query text, returns most similar chunk list
            权限 / Permission: knowledge_base:search
            """
            from app.ai.rag.retriever import VectorRetriever

            kb_service = KnowledgeBaseService(db, tenant_admin.tenant_id)
            kb = await kb_service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            retriever = VectorRetriever(db, tenant_admin.tenant_id)

            results = await retriever.search(
                knowledge_base=kb,
                query=data.query,
                top_k=data.top_k,
                score_threshold=data.score_threshold,
                search_mode=data.search_mode,
            )

            return success(data=[
                {
                    "chunk_id": r.chunk_id,
                    "content": r.content,
                    "score": r.score,
                    "metadata": r.metadata,
                    "document_name": r.document_name,
                    "document_id": r.document_id,
                    "highlight": r.highlight,
                }
                for r in results
            ])


# 导出路由器 / Export router
router = TenantKnowledgeBaseController.get_router()

__all__ = ["router", "TenantKnowledgeBaseController"]
