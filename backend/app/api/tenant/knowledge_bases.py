"""
租户端知识库管理 API

提供知识库 CRUD、文档管理、检索测试等接口
"""

import hashlib
import os

from fastapi import Request, UploadFile, File, Form

from app.core.base_controller import TenantController
from app.core.deps import DbSession, ActiveTenantAdmin, QueryParams
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
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseSearchRequest,
    QAPairCreate,
)
from app.core.recycle_bin import register_tenant_recycle_bin_routes
from app.services.ai.knowledge_base_service import (
    KnowledgeBaseService,
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
    resource="knowledge_base",
    name="menu.tenant.knowledge_base",
    scope=PermissionScope.TENANT,
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
    租户知识库管理控制器

    提供知识库 CRUD、文档上传/管理、检索测试
    """

    prefix = "/ai/knowledge-bases"
    tags = [_("menu.tags.tenant_knowledge_base")]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        # 回收站路由必须在 /{id} 之前注册，避免路径冲突
        register_tenant_recycle_bin_routes(
            router=router,
            service_class=KnowledgeBaseService,
            resource_name="knowledge_base",
        )

        # ========================================
        # 知识库 CRUD
        # ========================================

        @router.get("/selectable", summary="获取可 @ 选择的知识库列表")
        @action_read("action.knowledge_base.selectable")
        async def list_selectable_knowledge_bases(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取租户端可 @ 选择的知识库列表

            返回 scope=tenant(本租户) + scope=global 的知识库（精简字段）

            权限: knowledge_base:selectable
            """
            from sqlalchemy import select, or_, and_
            from app.models.ai.knowledge_base import KnowledgeBase
            from app.enums.common import ResourceScopeEnum

            tenant_id = tenant_admin.tenant_id
            stmt = (
                select(KnowledgeBase)
                .where(
                    KnowledgeBase.is_deleted.is_(False),
                    or_(
                        and_(
                            KnowledgeBase.scope == ResourceScopeEnum.TENANT.value,
                            KnowledgeBase.tenant_id == tenant_id,
                        ),
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

        @router.get("", summary="获取知识库列表")
        @action_read("action.knowledge_base.list")
        async def list_knowledge_bases(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            query: QueryParams,
        ):
            """
            获取知识库列表

            支持 JSON:API 分页、筛选、排序
            权限: knowledge_base:list
            """
            service = KnowledgeBaseService(db, tenant_admin.tenant_id)
            items, total = await service.query_list(spec=query)

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
            获取知识库详情

            权限: knowledge_base:detail
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
            创建知识库

            权限: knowledge_base:create
            """
            service = KnowledgeBaseService(db, tenant_admin.tenant_id)
            kb = await service.create(data.model_dump(exclude_unset=True))
            await db.commit()

            return created(
                data=kb.to_dict(),
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
            更新知识库配置

            权限: knowledge_base:update
            """
            service = KnowledgeBaseService(db, tenant_admin.tenant_id)

            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            updated = await service.update(
                kb_id, data.model_dump(exclude_unset=True),
            )
            await db.commit()

            return success(
                data=updated.to_dict(),
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
            删除知识库（软删除，级联删除文档和分块）

            权限: knowledge_base:delete
            """
            service = KnowledgeBaseService(db, tenant_admin.tenant_id)

            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            await service.delete(kb_id)
            await db.commit()

            return deleted(message=_("knowledge_base.deleted"))

        # ========================================
        # 文档管理
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
            获取知识库下的文档列表

            权限: knowledge_base:document_list
            """
            # 验证知识库存在
            kb_service = KnowledgeBaseService(db, tenant_admin.tenant_id)
            kb = await kb_service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            doc_service = KnowledgeDocumentService(db, tenant_admin.tenant_id)

            # 添加知识库 ID 过滤
            if not query.filters:
                query.filters = {}
            query.filters["knowledge_base_id"] = kb_id

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
            上传文档到知识库

            复用附件系统存储文件，创建文档记录并触发 Celery 异步处理。

            支持格式: txt, md, pdf, docx, csv, html
            权限: knowledge_base:document_upload
            """
            from app.enums.attachment import AttachmentSource, AttachmentVisibility
            from app.services.tenant.attachment_service import AttachmentService

            # 验证知识库存在
            kb_service = KnowledgeBaseService(db, tenant_admin.tenant_id)
            kb = await kb_service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            # 配额检查
            await kb_service.check_document_quota(kb_id)

            # 验证文件类型
            filename = file.filename or "unnamed"
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise BusinessException(
                    message=_("knowledge_base.error.unsupported_file_type"),
                )

            file_type = ALLOWED_EXTENSIONS[ext]

            # 读取文件内容并计算哈希
            file_bytes = await file.read()
            file_hash = hashlib.md5(file_bytes).hexdigest()
            file_size = len(file_bytes)

            # 去重检查
            doc_service = KnowledgeDocumentService(db, tenant_admin.tenant_id)
            existing = await doc_service.get_by_kb_and_hash(kb_id, file_hash)
            if existing:
                raise BusinessException(
                    message=_("knowledge_base.error.document_exists"),
                )

            # 复用附件系统上传
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

            # 创建文档记录
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

            # 触发 Celery 异步处理
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
            获取文档详情

            权限: knowledge_base:document_detail
            """
            doc_service = KnowledgeDocumentService(db, tenant_admin.tenant_id)
            doc = await doc_service.get_by_id(doc_id)

            if not doc or doc.knowledge_base_id != kb_id:
                raise NotFoundException(
                    message=_("knowledge_base.error.document_not_found"),
                )

            return success(data=doc.to_dict())

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
            删除文档（级联删除分块）

            权限: knowledge_base:document_delete
            """
            doc_service = KnowledgeDocumentService(db, tenant_admin.tenant_id)
            doc = await doc_service.get_by_id(doc_id)

            if not doc or doc.knowledge_base_id != kb_id:
                raise NotFoundException(
                    message=_("knowledge_base.error.document_not_found"),
                )

            # 删除分块
            chunk_service = DocumentChunkService(db, tenant_admin.tenant_id)
            await chunk_service.delete_by_document(doc_id)

            # 删除文档
            await doc_service.delete(doc_id)

            # 更新知识库统计
            kb_service = KnowledgeBaseService(db, tenant_admin.tenant_id)
            await kb_service.update_statistics(kb_id)
            await db.commit()

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
            重试失败的文档处理（断点续传）

            权限: knowledge_base:document_retry
            """
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

            # 重置为 pending 保留 error_stage（供断点续传）
            doc.status = DocumentStatusEnum.PENDING.value
            await db.commit()

            # 触发 Celery 重新处理
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
            获取文档实时处理进度（Redis）

            权限: knowledge_base:document_progress
            """
            from app.ai.rag.processor import get_document_progress as _get_progress

            doc_service = KnowledgeDocumentService(db, tenant_admin.tenant_id)
            doc = await doc_service.get_by_id(doc_id)

            if not doc or doc.knowledge_base_id != kb_id:
                raise NotFoundException(
                    message=_("knowledge_base.error.document_not_found"),
                )

            # 从 Redis 获取实时进度
            progress = await _get_progress(doc_id)
            if progress is None:
                # 回退到数据库状态
                progress = {
                    "stage": doc.status,
                    "progress": 100 if doc.status == "completed" else 0,
                    "total_chunks": doc.chunk_count,
                    "processed_chunks": doc.chunk_count if doc.status == "completed" else 0,
                }

            return success(data=progress)

        # ========================================
        # 重索引
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
            重新向量化知识库所有文档

            删除现有分块并重新触发处理
            权限: knowledge_base:reindex
            """
            kb_service = KnowledgeBaseService(db, tenant_admin.tenant_id)
            count = await kb_service.reindex_knowledge_base(kb_id)

            return success(
                data={"document_count": count},
                message=_("knowledge_base.reindex_started"),
            )

        # ========================================
        # Q&A 问答对
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
            手动添加 Q&A 问答对

            直接创建文档记录并生成对应 chunk，无需上传文件
            权限: knowledge_base:qa_create
            """
            import hashlib

            kb_service = KnowledgeBaseService(db, tenant_admin.tenant_id)
            kb = await kb_service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            # 配额检查
            await kb_service.check_document_quota(kb_id)

            # 构建 Q&A 内容
            qa_content = f"Q: {data.question}\nA: {data.answer}"
            content_hash = hashlib.md5(qa_content.encode("utf-8")).hexdigest()

            # 去重检查
            doc_service = KnowledgeDocumentService(db, tenant_admin.tenant_id)
            existing = await doc_service.get_by_kb_and_hash(kb_id, content_hash)
            if existing:
                raise BusinessException(
                    message=_("knowledge_base.document.error.duplicate"),
                )

            # 创建文档记录
            doc = await doc_service.create({
                "knowledge_base_id": kb_id,
                "file_name": f"qa_{content_hash[:8]}.txt",
                "file_type": DocumentTypeEnum.QA.value,
                "file_size": len(qa_content.encode("utf-8")),
                "file_hash": content_hash,
                "status": DocumentStatusEnum.COMPLETED.value,
                "chunk_count": 1,
                "char_count": len(qa_content),
            })

            # 直接创建 chunk（无需 Celery 异步）
            from app.ai.rag.embedding import EmbeddingService
            from app.ai.utils.token_estimator import estimate_tokens

            chunk_service = DocumentChunkService(db, tenant_admin.tenant_id)

            # 生成 embedding
            embedding_service = EmbeddingService(db, tenant_admin.tenant_id)
            embeddings = await embedding_service.generate_embedding(kb, qa_content)

            token_count = estimate_tokens(qa_content)

            await chunk_service.create({
                "document_id": doc.id,
                "knowledge_base_id": kb_id,
                "chunk_index": 0,
                "content": qa_content,
                "embedding": embeddings,
                "char_count": len(qa_content),
                "token_count": token_count,
                "metadata_": {
                    "type": "qa",
                    "question": data.question,
                    "answer": data.answer,
                },
            })

            # 更新文档 token_count
            doc.token_count = token_count

            # 更新知识库统计
            await kb_service.update_statistics(kb_id)
            await db.commit()

            return created(
                data=doc.to_dict(),
                message=_("knowledge_base.document.uploaded"),
            )

        # ========================================
        # 检索测试
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
            知识库检索测试

            输入查询文本，返回最相似的分块列表
            权限: knowledge_base:search
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


# 导出路由器
router = TenantKnowledgeBaseController.get_router()

__all__ = ["router", "TenantKnowledgeBaseController"]
