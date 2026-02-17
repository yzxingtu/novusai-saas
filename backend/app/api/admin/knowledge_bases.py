"""
知识库监控 API (Admin)

提供平台端知识库全局查询、统计监控、文档管理、检索测试等接口（平台管理员专用）
"""

import hashlib
import os

from fastapi import Request, UploadFile, File

from app.core.base_controller import GlobalController
from app.core.base_schema import PageResponse
from app.core.deps import DbSession, QueryParams, ActiveAdmin
from app.core.i18n import _
from app.core.response import success, created, deleted, paginated
from app.enums.knowledge_base import DocumentStatusEnum, DocumentTypeEnum
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException, BusinessException
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_create,
    action_update,
    action_delete,
)
from app.schemas.ai.knowledge_base import (
    AdminKnowledgeBaseCreate,
    AdminKnowledgeBaseUpdate,
    KnowledgeBaseSearchRequest,
)
from app.schemas.common.query import FilterRule, FilterOp
from app.services.ai.knowledge_base_service import (
    AdminKnowledgeBaseService,
    KnowledgeDocumentService,
    DocumentChunkService,
)

# 支持的文件类型映射
ALLOWED_EXTENSIONS: dict[str, str] = {
    ".txt": DocumentTypeEnum.TXT.value,
    ".md": DocumentTypeEnum.MD.value,
    ".pdf": DocumentTypeEnum.PDF.value,
    ".docx": DocumentTypeEnum.DOCX.value,
    ".csv": DocumentTypeEnum.CSV.value,
}


@permission_resource(
    resource="ai_knowledge_base",
    name="menu.admin.ai_knowledge_base",
    scope=PermissionScope.ADMIN,
    menu=MenuConfig(
        icon="lucide:book-open",
        path="/ai/monitor/knowledge-bases",
        component="ai/knowledge-bases/index",
        parent="ai_app",
        sort_order=40,
    ),
)
class AdminKnowledgeBaseController(GlobalController):
    """
    平台端知识库监控控制器

    提供全租户知识库查询和统计
    """

    prefix = "/ai/knowledge-bases"
    tags = [_("menu.tags.admin_ai_knowledge_base")]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        @router.get("", summary="查询知识库列表（全租户）")
        @action_read("action.ai_knowledge_base.list")
        async def list_knowledge_bases(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            admin: ActiveAdmin,
        ):
            """
            查询全部租户的知识库列表

            支持 JSON:API 风格筛选:
            - filter[tenant_id][eq]: 租户 ID
            - filter[status][eq]: 状态
            - filter[name][ilike]: 名称模糊搜索

            权限: ai_knowledge_base:list
            """
            service = AdminKnowledgeBaseService(db)
            items, total = await service.query_list(spec)

            result = []
            for kb in items:
                item = kb.to_dict()
                item["embedding_model_name"] = None
                try:
                    if kb.embedding_model:
                        item["embedding_model_name"] = kb.embedding_model.name
                except Exception:
                    pass
                result.append(item)

            return success(
                data=PageResponse.create(
                    items=result,
                    total=total,
                    page=spec.page,
                    page_size=spec.size,
                ),
                message=_("common.success"),
            )

        @router.post("", summary="创建知识库（支持全局/租户/管理端专属）")
        @action_create("action.ai_knowledge_base.create")
        async def create_knowledge_base(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            body: AdminKnowledgeBaseCreate,
        ):
            """
            管理端创建知识库

            支持 3 种 scope:
            - tenant: 属于指定租户（需提供 tenant_id）
            - global: 全局共享（所有租户可见）
            - admin: 仅管理端可见

            权限: ai_knowledge_base:create
            """
            service = AdminKnowledgeBaseService(db)
            data = body.model_dump(exclude_unset=True)
            kb = await service.create(data)
            await db.commit()
            await db.refresh(kb)

            result = kb.to_dict()
            result["embedding_model_name"] = None
            try:
                if kb.embedding_model:
                    result["embedding_model_name"] = kb.embedding_model.name
            except Exception:
                pass

            return created(data=result, message=_("knowledge_base.created"))

        @router.put("/{kb_id}", summary="更新知识库")
        @action_update("action.ai_knowledge_base.update")
        async def update_knowledge_base(
            request: Request,
            db: DbSession,
            kb_id: int,
            admin: ActiveAdmin,
            body: AdminKnowledgeBaseUpdate,
        ):
            """
            管理端更新知识库

            权限: ai_knowledge_base:update
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            data = body.model_dump(exclude_unset=True)
            kb = await service.update(kb_id, data)
            await db.commit()
            await db.refresh(kb)

            result = kb.to_dict()
            result["embedding_model_name"] = None
            try:
                if kb.embedding_model:
                    result["embedding_model_name"] = kb.embedding_model.name
            except Exception:
                pass

            return success(data=result, message=_("knowledge_base.updated"))

        @router.get("/selectable", summary="获取可 @ 选择的知识库列表")
        @action_read("action.ai_knowledge_base.selectable")
        async def list_selectable_knowledge_bases(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            """
            获取管理端可 @ 选择的知识库列表

            返回 scope=admin + scope=global 的知识库（精简字段）

            权限: ai_knowledge_base:selectable
            """
            from sqlalchemy import select, or_
            from app.models.ai.knowledge_base import KnowledgeBase
            from app.enums.common import ResourceScopeEnum

            stmt = (
                select(KnowledgeBase)
                .where(
                    KnowledgeBase.is_deleted.is_(False),
                    or_(
                        KnowledgeBase.scope == ResourceScopeEnum.ADMIN.value,
                        KnowledgeBase.scope == ResourceScopeEnum.GLOBAL.value,
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

        @router.get("/stats", summary="获取知识库全局统计")
        @action_read("action.ai_knowledge_base.stats")
        async def get_global_stats(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            """
            获取全局知识库统计

            返回总知识库数、总文档数、总分块数、总存储大小

            权限: ai_knowledge_base:stats
            """
            from sqlalchemy import select, func
            from app.models.ai.knowledge_base import KnowledgeBase

            stmt = select(
                func.count(KnowledgeBase.id).label("total_knowledge_bases"),
                func.coalesce(func.sum(KnowledgeBase.document_count), 0).label("total_documents"),
                func.coalesce(func.sum(KnowledgeBase.total_chunks), 0).label("total_chunks"),
                func.coalesce(func.sum(KnowledgeBase.total_size_bytes), 0).label("total_size_bytes"),
            ).where(KnowledgeBase.is_deleted.is_(False))

            result = await db.execute(stmt)
            row = result.one()

            return success(data={
                "total_knowledge_bases": row.total_knowledge_bases,
                "total_documents": row.total_documents,
                "total_chunks": row.total_chunks,
                "total_size_bytes": row.total_size_bytes,
            })

        @router.get("/{kb_id}", summary="获取知识库详情")
        @action_read("action.ai_knowledge_base.detail")
        async def get_knowledge_base_detail(
            request: Request,
            db: DbSession,
            kb_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取知识库详情

            权限: ai_knowledge_base:detail
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            result = kb.to_dict()
            result["embedding_model_name"] = None
            try:
                if kb.embedding_model:
                    result["embedding_model_name"] = kb.embedding_model.name
            except Exception:
                pass

            return success(data=result)

        # ========================================
        # 文档子资源
        # ========================================

        @router.get("/{kb_id}/documents", summary="获取文档列表（管理端）")
        @action_read("action.ai_knowledge_base.document_list")
        async def list_documents(
            request: Request,
            db: DbSession,
            kb_id: int,
            admin: ActiveAdmin,
            query: QueryParams,
        ):
            """
            获取知识库下的文档列表（跨租户）

            权限: ai_knowledge_base:document_list
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            doc_service = KnowledgeDocumentService(db, kb.tenant_id or 0)
            query.filters.append(FilterRule(
                field="knowledge_base_id", op=FilterOp.eq, value=str(kb_id)
            ))
            items, total = await doc_service.query_list(spec=query)

            return paginated(
                items=[doc.to_dict() for doc in items],
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.post("/{kb_id}/documents/upload", summary="上传文档（管理端）")
        @action_create("action.ai_knowledge_base.document_upload")
        async def upload_document(
            request: Request,
            db: DbSession,
            kb_id: int,
            admin: ActiveAdmin,
            file: UploadFile = File(..., description="上传的文档文件"),
        ):
            """
            上传文档到知识库

            权限: ai_knowledge_base:document_upload
            """
            from app.enums.attachment import AttachmentSource, AttachmentVisibility
            from app.services.tenant.attachment_service import AttachmentService

            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            tenant_id = kb.tenant_id or 0

            filename = file.filename or "unnamed"
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise BusinessException(
                    message=_("knowledge_base.error.unsupported_file_type"),
                )

            file_type = ALLOWED_EXTENSIONS[ext]
            file_bytes = await file.read()
            file_hash = hashlib.md5(file_bytes).hexdigest()
            file_size = len(file_bytes)

            doc_service = KnowledgeDocumentService(db, tenant_id)
            existing = await doc_service.get_by_kb_and_hash(kb_id, file_hash)
            if existing:
                raise BusinessException(
                    message=_("knowledge_base.error.document_exists"),
                )

            import io
            attachment_service = AttachmentService(db, tenant_id)
            upload_result = await attachment_service.upload_file(
                content=io.BytesIO(file_bytes),
                filename=filename,
                file_size=file_size,
                mime_type=file.content_type,
                visibility=AttachmentVisibility.PRIVATE,
                source=AttachmentSource.TENANT_ADMIN,
                uploader_id=admin.id,
                business_type="knowledge_document",
                business_id=kb_id,
            )

            attachment = upload_result["attachment"]

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

            from app.ai.rag.processor import process_document
            process_document.delay(
                tenant_id=tenant_id,
                document_id=doc.id,
            )

            return created(
                data=doc.to_dict(),
                message=_("knowledge_base.document.uploaded"),
            )

        @router.delete("/{kb_id}/documents/{doc_id}", summary="删除文档（管理端）")
        @action_delete("action.ai_knowledge_base.document_delete")
        async def delete_document(
            request: Request,
            db: DbSession,
            kb_id: int,
            doc_id: int,
            admin: ActiveAdmin,
        ):
            """
            删除文档（级联删除分块）

            权限: ai_knowledge_base:document_delete
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            tenant_id = kb.tenant_id or 0
            doc_service = KnowledgeDocumentService(db, tenant_id)
            doc = await doc_service.get_by_id(doc_id)

            if not doc or doc.knowledge_base_id != kb_id:
                raise NotFoundException(
                    message=_("knowledge_base.error.document_not_found"),
                )

            chunk_service = DocumentChunkService(db, tenant_id)
            await chunk_service.delete_by_document(doc_id)
            await doc_service.delete(doc_id)

            from app.services.ai.knowledge_base_service import KnowledgeBaseService
            kb_service = KnowledgeBaseService(db, tenant_id)
            await kb_service.update_statistics(kb_id)
            await db.commit()

            return deleted(message=_("knowledge_base.document.deleted"))

        @router.post(
            "/{kb_id}/documents/{doc_id}/retry",
            summary="重试失败文档（管理端）",
        )
        @action_update("action.ai_knowledge_base.document_retry")
        async def retry_document(
            request: Request,
            db: DbSession,
            kb_id: int,
            doc_id: int,
            admin: ActiveAdmin,
        ):
            """
            重试失败的文档处理

            权限: ai_knowledge_base:document_retry
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            tenant_id = kb.tenant_id or 0
            doc_service = KnowledgeDocumentService(db, tenant_id)
            doc = await doc_service.get_by_id(doc_id)

            if not doc or doc.knowledge_base_id != kb_id:
                raise NotFoundException(
                    message=_("knowledge_base.error.document_not_found"),
                )

            if doc.status != DocumentStatusEnum.ERROR.value:
                raise BusinessException(
                    message=_("knowledge_base.error.document_not_error"),
                )

            doc.status = DocumentStatusEnum.PENDING.value
            await db.commit()

            from app.ai.rag.processor import process_document
            process_document.delay(
                tenant_id=tenant_id,
                document_id=doc.id,
            )

            return success(
                data=doc.to_dict(),
                message=_("knowledge_base.document.retrying"),
            )

        @router.get(
            "/{kb_id}/documents/{doc_id}/progress",
            summary="获取文档处理进度（管理端）",
        )
        @action_read("action.ai_knowledge_base.document_progress")
        async def get_document_progress(
            request: Request,
            db: DbSession,
            kb_id: int,
            doc_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取文档实时处理进度

            权限: ai_knowledge_base:document_progress
            """
            from app.ai.rag.processor import get_document_progress as _get_progress

            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            tenant_id = kb.tenant_id or 0
            doc_service = KnowledgeDocumentService(db, tenant_id)
            doc = await doc_service.get_by_id(doc_id)

            if not doc or doc.knowledge_base_id != kb_id:
                raise NotFoundException(
                    message=_("knowledge_base.error.document_not_found"),
                )

            progress = await _get_progress(doc_id)
            if progress is None:
                progress = {
                    "stage": doc.status,
                    "progress": 100 if doc.status == "completed" else 0,
                    "total_chunks": doc.chunk_count,
                    "processed_chunks": doc.chunk_count if doc.status == "completed" else 0,
                }

            return success(data=progress)

        # ========================================
        # 重索引 & 检索测试
        # ========================================

        @router.post("/{kb_id}/reindex", summary="重新向量化知识库（管理端）")
        @action_update("action.ai_knowledge_base.reindex")
        async def reindex_knowledge_base(
            request: Request,
            db: DbSession,
            kb_id: int,
            admin: ActiveAdmin,
        ):
            """
            重新向量化知识库所有文档

            权限: ai_knowledge_base:reindex
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            from app.services.ai.knowledge_base_service import KnowledgeBaseService
            kb_service = KnowledgeBaseService(db, kb.tenant_id or 0)
            count = await kb_service.reindex_knowledge_base(kb_id)

            return success(
                data={"document_count": count},
                message=_("knowledge_base.reindex_started"),
            )

        @router.post("/{kb_id}/search", summary="检索测试（管理端）")
        @action_read("action.ai_knowledge_base.search")
        async def search_knowledge_base(
            request: Request,
            db: DbSession,
            kb_id: int,
            data: KnowledgeBaseSearchRequest,
            admin: ActiveAdmin,
        ):
            """
            知识库检索测试

            权限: ai_knowledge_base:search
            """
            from app.ai.rag.retriever import VectorRetriever

            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            tenant_id = kb.tenant_id or 0
            retriever = VectorRetriever(db, tenant_id)

            results = await retriever.search(
                knowledge_base=kb,
                query=data.query,
                top_k=data.top_k,
                score_threshold=data.score_threshold,
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

        # ========================================
        # 删除
        # ========================================

        @router.delete("/{kb_id}", summary="强制删除知识库")
        @action_delete("action.ai_knowledge_base.delete")
        async def delete_knowledge_base(
            request: Request,
            db: DbSession,
            kb_id: int,
            admin: ActiveAdmin,
        ):
            """
            强制删除知识库（平台管理权限）

            权限: ai_knowledge_base:delete
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            await service.delete(kb_id)
            await db.commit()

            return deleted(message=_("knowledge_base.deleted"))


# 导出路由器
router = AdminKnowledgeBaseController.get_router()

__all__ = ["router", "AdminKnowledgeBaseController"]
