"""
知识库监控 API (Admin) / Knowledge Base Monitoring API (Admin)

提供平台端知识库全局查询、统计监控、文档管理、检索测试等接口（平台管理员专用）
Provides platform-level knowledge base global query, statistics monitoring, document management, retrieval testing endpoints (platform admin only)
"""

import hashlib
import os

from fastapi import File, Form, Request, UploadFile

from app.core.base_controller import GlobalController
from app.core.base_schema import PageResponse
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import created, deleted, paginated, success
from app.enums.common import ResourceScopeEnum
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
from app.repositories.system.resource_tenant_assignment_repository import (
    ResourceTenantAssignmentRepository,
)
from app.schemas.ai.knowledge_base import (
    AdminKnowledgeBaseCreate,
    AdminKnowledgeBaseUpdate,
    KnowledgeBaseSearchRequest,
    QAPairCreate,
    TextDocumentCreate,
)
from app.schemas.common.query import FilterOp, FilterRule
from app.services.ai.knowledge_base_service import (
    AdminKnowledgeBaseService,
    DocumentChunkService,
    KnowledgeDocumentService,
)

SCOPES_NEEDING_ASSIGNMENT = (
    ResourceScopeEnum.SELECTED_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
)

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
    resource="ai_knowledge_base",
    name="menu.admin.ai_knowledge_base",
    scope=PermissionScope.ADMIN,
    parent_resource="ai_agent_mgmt",
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
    平台端知识库监控控制器 / Platform Knowledge Base Monitoring Controller

    提供全企业知识库查询和统计 / Provides cross-tenant knowledge base query and statistics
    """

    prefix = "/ai/knowledge-bases"
    tags = [_("menu.tags.admin_ai_knowledge_base")]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        # 回收站路由必须在 /{kb_id} 之前注册，避免路径冲突 / Recycle bin routes must be registered before /{kb_id} to avoid path conflicts
        from app.core.recycle_bin import register_admin_recycle_bin_routes
        register_admin_recycle_bin_routes(
            router=router,
            service_class=AdminKnowledgeBaseService,
            resource_name="ai_knowledge_base",
        )

        @router.get("", summary="查询知识库列表（全企业）")
        @action_read("action.ai_knowledge_base.list")
        async def list_knowledge_bases(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            admin: ActiveAdmin,
        ):
            """
            查询全部企业的知识库列表 / Query knowledge base list across all tenants

            支持 JSON:API 风格筛选 / Supports JSON:API style filtering:
            - filter[tenant_id][eq]: 企业 ID / Tenant ID
            - filter[status][eq]: 状态 / Status
            - filter[name][ilike]: 名称模糊搜索 / Name fuzzy search

            权限 / Permission: ai_knowledge_base:list
            """
            service = AdminKnowledgeBaseService(db)
            items, total = await service.query_list(spec)

            from app.api.shared._kb_helpers import enrich_model_names

            result = []
            for kb in items:
                item = kb.to_dict()
                enrich_model_names(kb, item)
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

        @router.post("", summary="创建知识库（支持全局/企业/管理端专属）")
        @action_create("action.ai_knowledge_base.create")
        async def create_knowledge_base(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            body: AdminKnowledgeBaseCreate,
        ):
            """
            管理端创建知识库 / Admin create knowledge base

            支持 3 种 scope / Supports 3 scopes:
            - tenant: 属于指定企业（需提供 tenant_id） / Belongs to specified tenant (requires tenant_id)
            - global: 全局共享（所有企业可见） / Global shared (visible to all tenants)
            - admin: 仅管理端可见 / Admin only visible

            权限 / Permission: ai_knowledge_base:create
            """
            service = AdminKnowledgeBaseService(db)
            data = body.model_dump(exclude_unset=True)
            tenant_ids = data.pop("tenant_ids", None)
            data.pop("assigned_tenant_ids", None)
            kb = await service.create(data)

            # selected_tenants / admin_and_selected_tenants 时同步企业分配 / Sync RTA for assignment scopes
            if kb.scope in SCOPES_NEEDING_ASSIGNMENT and tenant_ids is not None:
                repo = ResourceTenantAssignmentRepository(db)
                await repo.sync_assignments("knowledge_base", kb.id, tenant_ids)

            await db.commit()
            await db.refresh(kb)

            from app.api.shared._kb_helpers import enrich_model_names

            result = kb.to_dict()
            enrich_model_names(kb, result)
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
            管理端更新知识库 / Admin update knowledge base

            权限 / Permission: ai_knowledge_base:update
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            data = body.model_dump(exclude_unset=True)
            tenant_ids = data.pop("tenant_ids", None)
            data.pop("assigned_tenant_ids", None)
            kb = await service.update(kb_id, data)

            # 同步企业分配 / Sync tenant assignments
            effective_scope = kb.scope
            if effective_scope in SCOPES_NEEDING_ASSIGNMENT and tenant_ids is not None:
                repo = ResourceTenantAssignmentRepository(db)
                await repo.sync_assignments("knowledge_base", kb_id, tenant_ids)
            elif effective_scope not in SCOPES_NEEDING_ASSIGNMENT:
                # scope 不再需要分配，清理残留记录 / Scope no longer needs assignment, clean up residual records
                repo = ResourceTenantAssignmentRepository(db)
                await repo.delete_all_for_resource("knowledge_base", kb_id)

            await db.commit()
            await db.refresh(kb)

            from app.api.shared._kb_helpers import enrich_model_names

            result = kb.to_dict()
            enrich_model_names(kb, result)
            return success(data=result, message=_("knowledge_base.updated"))

        @router.get("/selectable", summary="获取可 @ 选择的知识库列表")
        @action_read("action.ai_knowledge_base.selectable")
        async def list_selectable_knowledge_bases(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            """
            获取管理端可 @ 选择的知识库列表 / Get knowledge base list selectable via @ in admin

            返回 scope=admin + scope=global 的知识库（精简字段）
            Returns knowledge bases with scope=admin + scope=global (simplified fields)

            权限 / Permission: ai_knowledge_base:selectable
            """
            from sqlalchemy import select

            from app.enums.common import ResourceScopeEnum
            from app.models.ai.knowledge_base import KnowledgeBase

            # 查询管理端可消费的知识库（admin_only / global_shared） / Admin-consumable KBs
            stmt = (
                select(KnowledgeBase)
                .where(
                    KnowledgeBase.is_deleted.is_(False),
                    KnowledgeBase.scope.in_([
                        ResourceScopeEnum.ADMIN_ONLY.value,
                        ResourceScopeEnum.GLOBAL_SHARED.value,
                    ]),
                )
                .order_by(KnowledgeBase.name.asc())
                .limit(500)
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
            获取全局知识库统计 / Get global knowledge base statistics

            返回总知识库数、总文档数、总分块数、总存储大小
            Returns total knowledge bases, total documents, total chunks, total storage size

            权限 / Permission: ai_knowledge_base:stats
            """
            from sqlalchemy import func, select

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
            获取知识库详情 / Get knowledge base details

            权限 / Permission: ai_knowledge_base:detail
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            from app.api.shared._kb_helpers import enrich_model_names

            result = kb.to_dict()
            enrich_model_names(kb, result)
            # 返回已分配的企业 ID 列表 / Return assigned tenant ID list
            if kb.scope in SCOPES_NEEDING_ASSIGNMENT:
                repo = ResourceTenantAssignmentRepository(db)
                result["assigned_tenant_ids"] = await repo.get_assigned_tenant_ids(
                    "knowledge_base", kb_id
                )
            else:
                result["assigned_tenant_ids"] = []

            return success(data=result)

        # ========================================
        # 文档子资源 / Document Sub-resources
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
            获取知识库下的文档列表（跨企业） / Get document list under knowledge base (cross-tenant)

            权限 / Permission: ai_knowledge_base:document_list
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            doc_service = KnowledgeDocumentService(db, kb.tenant_id)
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
            file: UploadFile = File(..., description=_("api.param.doc_file")),
        ):
            """
            上传文档到知识库 / Upload document to knowledge base

            权限 / Permission: ai_knowledge_base:document_upload
            """
            from app.enums.attachment import AttachmentSource, AttachmentVisibility
            from app.services.tenant.attachment_service import AttachmentService

            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            tenant_id = kb.tenant_id

            # 配额检查（per-KB 文档数量限制） / Quota check (per-KB document count limit)
            from app.services.ai.knowledge_base_service import KnowledgeBaseService
            kb_service = KnowledgeBaseService(db, tenant_id)
            await kb_service.check_document_quota(kb_id)

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

            if tenant_id is not None:
                # 企业 KB：通过 AttachmentService 上传（含企业配额校验） / Tenant KB: upload via AttachmentService (with tenant quota check)
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
            else:
                # 全局/管理端 KB：直接使用平台存储，跳过企业校验 / Global/admin KB: use platform storage directly, skip tenant validation
                from app.configs.service import ConfigService
                from app.models.tenant.attachment import Attachment as AttachmentModel
                from app.storage import storage_manager
                from app.storage.base import StorageConfig

                config_service = ConfigService(db)
                driver_name = await config_service.get_platform_config(
                    "platform_storage_driver", default="local"
                )
                if str(driver_name) == "local":
                    from app.storage import LOCAL_STORAGE_ROOT
                    root_path = str(LOCAL_STORAGE_ROOT)
                else:
                    root_path = str(await config_service.get_platform_config(
                        "platform_storage_root_path", default=""
                    ))
                base_url = await config_service.get_platform_config(
                    "platform_storage_base_url", default=None
                )
                options = await config_service.get_platform_config(
                    "platform_storage_options", default={}
                )
                storage_config = StorageConfig(
                    driver=str(driver_name),
                    root_path=root_path,
                    base_url=base_url,
                    options=options or {},
                )

                import uuid
                storage_path = f"knowledge-bases/admin/{kb_id}/{uuid.uuid4().hex}_{filename}"
                driver = storage_manager.get_driver(storage_config)
                await driver.put(storage_path, io.BytesIO(file_bytes))

                attachment = AttachmentModel(
                    tenant_id=None,
                    name=filename,
                    original_name=filename,
                    path=storage_path,
                    base_url=storage_config.base_url or "",
                    size=file_size,
                    mime_type=file.content_type or "application/octet-stream",
                    extension=ext,
                    hash=file_hash,
                    driver=str(driver_name),
                    visibility=AttachmentVisibility.PRIVATE.value,
                    source=AttachmentSource.TENANT_ADMIN.value,
                    uploader_id=admin.id,
                    business_type="knowledge_document",
                    business_id=kb_id,
                )
                db.add(attachment)
                await db.flush()

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

        @router.post("/{kb_id}/documents/text", summary="直接文本输入（管理端）")
        @action_create("action.ai_knowledge_base.document_text")
        async def create_text_document(
            request: Request,
            db: DbSession,
            kb_id: int,
            data: TextDocumentCreate,
            admin: ActiveAdmin,
        ):
            """
            直接输入文本内容创建文档 / Create document by direct text input

            将文本包装为虚拟 TXT 文件，走标准分块/Embedding 流程
            Wraps text as virtual TXT file, goes through standard chunking/embedding pipeline
            权限 / Permission: ai_knowledge_base:document_text
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            tenant_id = kb.tenant_id

            from app.services.ai.knowledge_base_service import KnowledgeBaseService
            kb_service = KnowledgeBaseService(db, tenant_id)
            await kb_service.check_document_quota(kb_id)

            content_bytes = data.content.encode("utf-8")
            content_hash = hashlib.md5(content_bytes).hexdigest()

            doc_service = KnowledgeDocumentService(db, tenant_id)
            existing = await doc_service.get_by_kb_and_hash(kb_id, content_hash)
            if existing:
                raise BusinessException(
                    message=_("knowledge_base.error.document_exists"),
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
                tenant_id=tenant_id,
                document_id=doc.id,
            )

            return created(
                data=doc.to_dict(),
                message=_("knowledge_base.document.uploaded"),
            )

        @router.get("/{kb_id}/documents/{doc_id}/chunks", summary="文档分块预览（管理端）")
        @action_read("action.ai_knowledge_base.document_chunks")
        async def get_document_chunks(
            request: Request,
            db: DbSession,
            kb_id: int,
            doc_id: int,
            admin: ActiveAdmin,
            page: int = 1,
            page_size: int = 20,
        ):
            """
            获取文档的分块列表（预览用） / Get document chunk list (for preview)

            权限 / Permission: ai_knowledge_base:document_chunks
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            tenant_id = kb.tenant_id
            doc_service = KnowledgeDocumentService(db, tenant_id)
            doc = await doc_service.get_by_id(doc_id)
            if not doc or doc.knowledge_base_id != kb_id:
                raise NotFoundException(
                    message=_("knowledge_base.error.document_not_found"),
                )

            chunk_service = DocumentChunkService(db, tenant_id)
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
            删除文档（级联删除分块） / Delete document (cascade delete chunks)

            权限 / Permission: ai_knowledge_base:document_delete
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            tenant_id = kb.tenant_id
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

            from app.ai.rag.retriever import HybridRetriever
            await HybridRetriever.invalidate_kb_cache(kb_id)

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
            重试失败的文档处理 / Retry failed document processing

            权限 / Permission: ai_knowledge_base:document_retry
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            tenant_id = kb.tenant_id
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
            获取文档实时处理进度 / Get real-time document processing progress

            权限 / Permission: ai_knowledge_base:document_progress
            """
            from app.ai.rag.processor import get_document_progress as _get_progress

            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            tenant_id = kb.tenant_id
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
        # 重索引 & 检索测试 / Re-index & Retrieval Testing
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
            重新向量化知识库所有文档 / Re-vectorize all documents in knowledge base

            权限 / Permission: ai_knowledge_base:reindex
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            from app.services.ai.knowledge_base_service import KnowledgeBaseService
            kb_service = KnowledgeBaseService(db, kb.tenant_id)
            count = await kb_service.reindex_knowledge_base(kb_id)

            from app.ai.rag.retriever import HybridRetriever
            await HybridRetriever.invalidate_kb_cache(kb_id)

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
            知识库检索测试 / Knowledge base retrieval test

            权限 / Permission: ai_knowledge_base:search
            """
            from app.ai.rag.retriever import VectorRetriever

            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            tenant_id = kb.tenant_id
            retriever = VectorRetriever(db, tenant_id)

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

        # ========================================
        # Q&A 问答对 / Q&A Pairs
        # ========================================

        @router.post("/{kb_id}/qa-pairs", summary="添加 Q&A 问答对（管理端）")
        @action_create("action.ai_knowledge_base.qa_create")
        async def create_qa_pair(
            request: Request,
            db: DbSession,
            kb_id: int,
            data: QAPairCreate,
            admin: ActiveAdmin,
        ):
            """
            手动添加 Q&A 问答对 / Manually add Q&A pair

            直接创建文档记录并生成对应 chunk，无需上传文件
            Directly creates document record and generates corresponding chunk, no file upload needed
            权限 / Permission: ai_knowledge_base:qa_create
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            tenant_id = kb.tenant_id

            # 配额检查 / Quota check
            from app.services.ai.knowledge_base_service import KnowledgeBaseService
            kb_service = KnowledgeBaseService(db, tenant_id)
            await kb_service.check_document_quota(kb_id)

            # 构建 Q&A 内容 / Build Q&A content
            qa_content = f"Q: {data.question}\nA: {data.answer}"
            content_hash = hashlib.md5(qa_content.encode("utf-8")).hexdigest()

            # 去重检查 / Deduplication check
            doc_service = KnowledgeDocumentService(db, tenant_id)
            existing = await doc_service.get_by_kb_and_hash(kb_id, content_hash)
            if existing:
                raise BusinessException(
                    message=_("knowledge_base.document.error.duplicate"),
                )

            # 创建文档记录（metadata_extra 存储原始 Q&A JSON，供 reindex 使用） / Create document record (metadata_extra stores original Q&A JSON for reindex)
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

            chunk_service = DocumentChunkService(db, tenant_id)

            embedding_service = EmbeddingService(db, tenant_id)
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

            doc.token_count = token_count
            await kb_service.update_statistics(kb_id)
            await db.commit()

            from app.ai.rag.retriever import HybridRetriever
            await HybridRetriever.invalidate_kb_cache(kb_id)

            return created(
                data=doc.to_dict(),
                message=_("knowledge_base.document.uploaded"),
            )

        @router.post("/{kb_id}/qa-pairs/batch", summary="批量导入 Q&A 问答对（管理端）")
        @action_create("action.ai_knowledge_base.qa_batch")
        async def batch_import_qa(
            request: Request,
            db: DbSession,
            kb_id: int,
            admin: ActiveAdmin,
            file: UploadFile = File(..., description=_("api.param.qa_file")),
        ):
            """
            批量导入 Q&A 问答对（CSV/Excel） / Batch import Q&A pairs (CSV/Excel)

            文件需包含 question 和 answer 两列，每行创建一条 Q&A 文档+chunk。
            File must contain question and answer columns, each row creates one Q&A document+chunk.
            权限 / Permission: ai_knowledge_base:qa_batch
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            tenant_id = kb.tenant_id
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

            doc_service = KnowledgeDocumentService(db, tenant_id)
            chunk_service = DocumentChunkService(db, tenant_id)
            embedding_service = EmbeddingService(db, tenant_id)

            from app.services.ai.knowledge_base_service import KnowledgeBaseService
            kb_service = KnowledgeBaseService(db, tenant_id)

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
        # URL 网页导入 / URL Web Import
        # ========================================

        @router.post("/{kb_id}/documents/url", summary="URL 网页导入（管理端）")
        @action_create("action.ai_knowledge_base.document_url")
        async def import_from_url(
            request: Request,
            db: DbSession,
            kb_id: int,
            admin: ActiveAdmin,
            urls: list[str] = Form(..., description=_("api.param.urls")),
        ):
            """
            通过 URL 导入网页内容 / Import web content via URL

            每个 URL 创建一个文档，异步爬取和处理。
            Each URL creates a document, crawled and processed asynchronously.
            权限 / Permission: ai_knowledge_base:document_url
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            tenant_id = kb.tenant_id
            doc_service = KnowledgeDocumentService(db, tenant_id)
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
                    tenant_id=tenant_id,
                    document_id=doc_dict["id"],
                )

            return success(data={
                "created": len(created_docs),
                "documents": created_docs,
            })

        # ========================================
        # 删除 / Delete
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
            强制删除知识库（平台管理权限） / Force delete knowledge base (platform admin permission)

            权限 / Permission: ai_knowledge_base:delete
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            await service.delete(kb_id)
            await db.commit()

            return deleted(message=_("knowledge_base.deleted"))


# 导出路由器 / Export router
router = AdminKnowledgeBaseController.get_router()

__all__ = ["router", "AdminKnowledgeBaseController"]
