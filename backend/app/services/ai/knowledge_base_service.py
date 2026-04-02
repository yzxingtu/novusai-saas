"""
知识库 Service / Knowledge Base Service

提供知识库的创建、更新、删除等业务逻辑
Provides knowledge base create, update, delete business logic.
"""

from typing import Any

from sqlalchemy import and_, select, update

from app.core.base_model import utc_now
from app.core.base_service import GlobalService, TenantService
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.common import RecycleStageEnum, ResourceScopeEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.document_chunk import DocumentChunk
from app.models.ai.knowledge_base import KnowledgeBase
from app.models.ai.knowledge_document import KnowledgeDocument
from app.repositories.ai.knowledge_base_repository import (
    AdminKnowledgeBaseRepository,
    DocumentChunkRepository,
    KnowledgeBaseRepository,
    KnowledgeDocumentRepository,
)

logger = LogManager.get_logger("ai.knowledge_base_service")


# 默认知识库配额 / Default knowledge-base quota
DEFAULT_MAX_KNOWLEDGE_BASES = 20
DEFAULT_MAX_DOCUMENTS_PER_KB = 500


class KnowledgeBaseService(TenantService[KnowledgeBase, KnowledgeBaseRepository]):
    """
    企业级知识库 Service / Tenant knowledge base service.
    提供知识库的创建、更新、删除、统计更新、配额检查等业务逻辑 / CRUD, stats update, quota checks.
    """

    model = KnowledgeBase
    repository_class = KnowledgeBaseRepository

    async def _before_create(self, data: dict[str, Any]) -> None:
        """创建前校验：名称唯一性 + 配额检查 / Before create: name uniqueness + quota check."""
        await super()._before_create(data)

        # 配额检查 / Quota check
        await self.check_kb_quota()

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name(name)
            if existing:
                raise BusinessException(message=_("knowledge_base.error.name_exists"))

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        """更新前校验：scope 保护、名称唯一性 / Before update: scope protection, name uniqueness."""
        await super()._before_update(id, data)

        kb = await self.repo.get_by_id(id)
        if not kb:
            raise NotFoundException(message=_("knowledge_base.error.not_found"))

        # 企业端只能修改自有知识库（owner_tenant_id 与当前企业匹配）
        if kb.owner_tenant_id != self.repo.tenant_id:
            raise BusinessException(message=_("knowledge_base.error.readonly"))

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name(name, exclude_id=id)
            if existing:
                raise BusinessException(message=_("knowledge_base.error.name_exists"))

    async def _before_delete(self, id: int) -> None:
        """删除前：scope 保护、级联软删除文档和分块 / Before delete: scope protection, cascade soft-delete docs and chunks."""
        await super()._before_delete(id)

        kb = await self.repo.get_by_id(id)
        if not kb:
            raise NotFoundException(message=_("knowledge_base.error.not_found"))

        # 企业端只能删除自有知识库（owner_tenant_id 与当前企业匹配）
        if kb.owner_tenant_id != self.repo.tenant_id:
            raise BusinessException(message=_("knowledge_base.error.readonly"))

        level = self._default_delete_level
        now = utc_now()
        # 级联软删除文档分块 / Cascade soft-delete document chunks
        doc_ids_query = select(KnowledgeDocument.id).where(
            KnowledgeDocument.knowledge_base_id == id,
            KnowledgeDocument.is_deleted.is_(False),
        )
        await self.repo.db.execute(
            update(DocumentChunk)
            .where(
                DocumentChunk.document_id.in_(doc_ids_query),
                DocumentChunk.is_deleted.is_(False),
            )
            .values(
                is_deleted=True,
                deleted_at=now,
                delete_level=level,
                recycle_stage=RecycleStageEnum.MODULE.value,
                promoted_to_global_at=None,
                updated_at=now,
            )
        )
        # 级联软删除文档 / Cascade soft-delete documents
        await self.repo.db.execute(
            update(KnowledgeDocument)
            .where(
                KnowledgeDocument.knowledge_base_id == id,
                KnowledgeDocument.is_deleted.is_(False),
            )
            .values(
                is_deleted=True,
                deleted_at=now,
                delete_level=level,
                recycle_stage=RecycleStageEnum.MODULE.value,
                promoted_to_global_at=None,
                updated_at=now,
            )
        )

    async def promote_to_global(self, id: int) -> KnowledgeBase | None:
        """推进到总回收站，级联推进文档和分块 / Promote to global recycle bin and cascade docs/chunks."""
        instance = await self.repo.promote_to_global_by_id(
            id,
            delete_level=self._default_delete_level,
        )
        if instance is None:
            return None

        now = utc_now()
        doc_ids_query = select(KnowledgeDocument.id).where(
            KnowledgeDocument.knowledge_base_id == id,
            KnowledgeDocument.is_deleted.is_(True),
        )
        await self.repo.db.execute(
            update(DocumentChunk)
            .where(
                DocumentChunk.document_id.in_(doc_ids_query),
                DocumentChunk.is_deleted.is_(True),
            )
            .values(
                recycle_stage=RecycleStageEnum.GLOBAL.value,
                promoted_to_global_at=now,
                updated_at=now,
            )
        )
        await self.repo.db.execute(
            update(KnowledgeDocument)
            .where(
                KnowledgeDocument.knowledge_base_id == id,
                KnowledgeDocument.is_deleted.is_(True),
            )
            .values(
                recycle_stage=RecycleStageEnum.GLOBAL.value,
                promoted_to_global_at=now,
                updated_at=now,
            )
        )
        return instance

    async def _after_restore(self, instance: KnowledgeBase) -> None:
        """恢复后：级联恢复文档和分块 / After restore: cascade restore docs and chunks."""
        now = utc_now()
        # 级联恢复文档 / Cascade restore documents
        await self.repo.db.execute(
            update(KnowledgeDocument)
            .where(
                KnowledgeDocument.knowledge_base_id == instance.id,
                KnowledgeDocument.is_deleted.is_(True),
            )
            .values(
                is_deleted=False,
                deleted_at=None,
                delete_level=None,
                recycle_stage=None,
                promoted_to_global_at=None,
                updated_at=now,
            )
        )
        # 级联恢复文档分块 / Cascade restore document chunks
        doc_ids_query = select(KnowledgeDocument.id).where(
            KnowledgeDocument.knowledge_base_id == instance.id,
        )
        await self.repo.db.execute(
            update(DocumentChunk)
            .where(
                DocumentChunk.document_id.in_(doc_ids_query),
                DocumentChunk.is_deleted.is_(True),
            )
            .values(
                is_deleted=False,
                deleted_at=None,
                delete_level=None,
                recycle_stage=None,
                promoted_to_global_at=None,
                updated_at=now,
            )
        )
        await self.repo.update_statistics(instance.id)
        from app.ai.rag.retriever import HybridRetriever
        await HybridRetriever.invalidate_kb_cache(instance.id)

    async def get_kb_detail(self, kb_id: int) -> dict[str, Any]:
        """
        获取知识库详情（含关联 Embedding 模型信息） / Get KB detail (with embedding/vision model info).

        Args:
            kb_id: 知识库 ID / Knowledge base ID.

        Returns:
            包含模型名称的知识库字典 / KB dict with model names.
        """
        kb = await self.repo.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message=_("knowledge_base.error.not_found"))

        result = kb.to_dict()
        result["embedding_model_name"] = None
        result["vision_model_name"] = None
        result["audio_model_name"] = None
        result["video_model_name"] = None

        try:
            model_obj = getattr(kb, "embedding_model", None)
            if model_obj is not None:
                result["embedding_model_name"] = model_obj.name
        except AttributeError:
            pass

        try:
            vision_obj = getattr(kb, "vision_model", None)
            if vision_obj is not None:
                result["vision_model_name"] = vision_obj.name
        except AttributeError:
            pass

        try:
            audio_obj = getattr(kb, "audio_model", None)
            if audio_obj is not None:
                result["audio_model_name"] = audio_obj.name
        except AttributeError:
            pass

        try:
            video_obj = getattr(kb, "video_model", None)
            if video_obj is not None:
                result["video_model_name"] = video_obj.name
        except AttributeError:
            pass

        return result

    async def update_statistics(self, kb_id: int) -> None:
        """
        重新计算知识库统计 / Recompute KB statistics.

        Args:
            kb_id: 知识库 ID / Knowledge base ID.
        """
        await self.repo.update_statistics(kb_id)

    async def check_kb_quota(self) -> None:
        """检查企业知识库数量配额 / Check tenant KB count quota."""
        count = await self.repo.count_by_tenant()
        if count >= DEFAULT_MAX_KNOWLEDGE_BASES:
            raise BusinessException(
                message=_("knowledge_base.error.quota_exceeded"),
            )

    async def check_document_quota(self, kb_id: int) -> None:
        """检查知识库文档数量配额 / Check KB document count quota."""
        kb = await self.repo.get_by_id(kb_id)
        if kb and kb.document_count >= DEFAULT_MAX_DOCUMENTS_PER_KB:
            raise BusinessException(
                message=_("knowledge_base.error.document_limit_exceeded"),
            )

    async def reindex_knowledge_base(self, kb_id: int) -> int:
        """
        重新向量化知识库所有文档 / Reindex all documents in KB.
        删除所有现有 chunks，重新触发 process_document / Delete existing chunks, re-trigger process_document.

        Args:
            kb_id: 知识库 ID / Knowledge base ID.

        Returns:
            触发的文档数量 / Number of documents triggered.
        """
        from app.enums.knowledge_base import DocumentStatusEnum

        kb = await self.repo.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message=_("knowledge_base.error.not_found"))

        # 查询所有未删除文档 / Query all non-deleted documents
        stmt = select(KnowledgeDocument).where(
            and_(
                KnowledgeDocument.knowledge_base_id == kb_id,
                KnowledgeDocument.tenant_id == self.repo.tenant_id,
                KnowledgeDocument.is_deleted.is_(False),
            )
        )
        result = await self.db.execute(stmt)
        docs = list(result.scalars().all())

        if not docs:
            return 0

        # 重置文档状态并触发重新处理 / Reset document state and reprocess
        from app.ai.rag.processor import process_document

        count = 0
        for doc in docs:
            doc.status = DocumentStatusEnum.PENDING.value
            doc.error_message = None
            doc.error_stage = None
            doc.chunk_count = 0
            doc.token_count = 0
            doc.char_count = 0
            count += 1

        await self.db.commit()

        # 异步触发 Celery 任务
        for doc in docs:
            process_document.delay(
                tenant_id=self.repo.tenant_id,
                document_id=doc.id,
            )

        logger.info(
            "Reindex triggered: kb={}, docs={}",
            kb_id, count,
        )

        return count


class KnowledgeDocumentService(TenantService[KnowledgeDocument, KnowledgeDocumentRepository]):
    """
    企业级知识文档 Service / Tenant knowledge document service.
    """

    model = KnowledgeDocument
    repository_class = KnowledgeDocumentRepository

    async def get_by_kb_and_hash(
        self,
        knowledge_base_id: int,
        file_hash: str,
    ) -> KnowledgeDocument | None:
        """检查文件是否已存在（去重） / Check if file already exists (dedup by hash)."""
        return await self.repo.get_by_kb_and_hash(knowledge_base_id, file_hash)

    async def update_status(
        self,
        doc_id: int,
        status: str,
        error_message: str | None = None,
        error_stage: str | None = None,
    ) -> None:
        """更新文档处理状态 / Update document processing status."""
        await self.repo.update_status(doc_id, status, error_message, error_stage)


class DocumentChunkService(TenantService[DocumentChunk, DocumentChunkRepository]):
    """
    企业级文档分块 Service / Tenant document chunk service.
    """

    model = DocumentChunk
    repository_class = DocumentChunkRepository

    async def delete_by_document(self, document_id: int) -> int:
        """删除指定文档的所有分块 / Delete all chunks for document."""
        return await self.repo.delete_by_document(document_id)

    async def get_by_document(
        self,
        document_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> list[DocumentChunk]:
        """获取指定文档的分块列表 / Get chunk list for document."""
        return await self.repo.get_by_document(document_id, skip, limit)

    async def list_document_chunks(
        self,
        *,
        document_id: int,
        page: int,
        page_size: int,
    ) -> list[DocumentChunk]:
        """分页获取文档分块 / Get paginated document chunks."""
        return await self.get_by_document(
            document_id=document_id,
            skip=(page - 1) * page_size,
            limit=page_size,
        )


class AdminKnowledgeBaseService(GlobalService[KnowledgeBase, AdminKnowledgeBaseRepository]):
    """
    管理端知识库 Service / Admin knowledge base service.
    无企业隔离，供平台管理端全局查询和 CRUD 使用 / No tenant isolation, for admin CRUD.
    """

    model = KnowledgeBase
    repository_class = AdminKnowledgeBaseRepository

    async def _before_create(self, data: dict[str, Any]) -> None:
        """创建前校验：scope + owner_tenant_id、名称唯一性 / Before create: scope, owner, name uniqueness."""
        await super()._before_create(data)

        scope = data.get("scope", ResourceScopeEnum.GLOBAL_SHARED.value)
        data.pop("visibility", None)
        data.pop("assigned_tenant_ids", None)
        data.pop("tenant_ids", None)
        if data.get("tenant_id") is not None and data.get("owner_tenant_id") is None:
            data["owner_tenant_id"] = data.pop("tenant_id")
        else:
            data.pop("tenant_id", None)

        owner_tid = data.get("owner_tenant_id")
        name = data.get("name")
        if name:
            existing = await self._check_name_unique(
                name, owner_tenant_id=owner_tid, scope=scope,
            )
            if existing:
                raise BusinessException(message=_("knowledge_base.error.name_exists"))

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        """更新前校验：scope 变更时的一致性、名称唯一性 / Before update: scope consistency, name uniqueness."""
        await super()._before_update(id, data)

        kb = await self.repo.get_by_id(id)
        if not kb:
            raise NotFoundException(message=_("knowledge_base.error.not_found"))

        scope = data.get("scope", kb.scope)
        data.pop("visibility", None)
        data.pop("assigned_tenant_ids", None)
        data.pop("tenant_ids", None)
        if data.get("tenant_id") is not None and data.get("owner_tenant_id") is None:
            data["owner_tenant_id"] = data.pop("tenant_id")
        else:
            data.pop("tenant_id", None)

        owner_tid = data.get("owner_tenant_id", kb.owner_tenant_id)
        name = data.get("name")
        if name:
            existing = await self._check_name_unique(
                name, owner_tenant_id=owner_tid, scope=scope, exclude_id=id,
            )
            if existing:
                raise BusinessException(message=_("knowledge_base.error.name_exists"))

    async def _before_delete(self, id: int) -> None:
        """删除前：级联软删除文档和分块，清理企业分配 / Before delete: cascade soft-delete docs/chunks, clear tenant assignments."""
        await super()._before_delete(id)

        level = self._default_delete_level
        now = utc_now()
        doc_ids_query = select(KnowledgeDocument.id).where(
            KnowledgeDocument.knowledge_base_id == id,
            KnowledgeDocument.is_deleted.is_(False),
        )
        await self.repo.db.execute(
            update(DocumentChunk)
            .where(
                DocumentChunk.document_id.in_(doc_ids_query),
                DocumentChunk.is_deleted.is_(False),
            )
            .values(
                is_deleted=True,
                deleted_at=now,
                delete_level=level,
                recycle_stage=RecycleStageEnum.MODULE.value,
                promoted_to_global_at=None,
                updated_at=now,
            )
        )
        await self.repo.db.execute(
            update(KnowledgeDocument)
            .where(
                KnowledgeDocument.knowledge_base_id == id,
                KnowledgeDocument.is_deleted.is_(False),
            )
            .values(
                is_deleted=True,
                deleted_at=now,
                delete_level=level,
                recycle_stage=RecycleStageEnum.MODULE.value,
                promoted_to_global_at=None,
                updated_at=now,
            )
        )

        from app.repositories.system.resource_tenant_assignment_repository import (
            ResourceTenantAssignmentRepository,
        )
        rta_repo = ResourceTenantAssignmentRepository(self.db)
        await rta_repo.delete_all_for_resource("knowledge_base", id)

    async def promote_to_global(self, id: int) -> KnowledgeBase | None:
        """推进到总回收站，级联推进文档和分块 / Promote to global recycle bin and cascade docs/chunks."""
        instance = await self.repo.promote_to_global_by_id(
            id,
            delete_level=self._default_delete_level,
        )
        if instance is None:
            return None

        now = utc_now()
        doc_ids_query = select(KnowledgeDocument.id).where(
            KnowledgeDocument.knowledge_base_id == id,
            KnowledgeDocument.is_deleted.is_(True),
        )
        await self.repo.db.execute(
            update(DocumentChunk)
            .where(
                DocumentChunk.document_id.in_(doc_ids_query),
                DocumentChunk.is_deleted.is_(True),
            )
            .values(
                recycle_stage=RecycleStageEnum.GLOBAL.value,
                promoted_to_global_at=now,
                updated_at=now,
            )
        )
        await self.repo.db.execute(
            update(KnowledgeDocument)
            .where(
                KnowledgeDocument.knowledge_base_id == id,
                KnowledgeDocument.is_deleted.is_(True),
            )
            .values(
                recycle_stage=RecycleStageEnum.GLOBAL.value,
                promoted_to_global_at=now,
                updated_at=now,
            )
        )
        return instance

    async def _after_restore(self, instance: KnowledgeBase) -> None:
        """恢复后：级联恢复文档和分块 / After restore: cascade restore docs and chunks."""
        now = utc_now()
        await self.repo.db.execute(
            update(KnowledgeDocument)
            .where(
                KnowledgeDocument.knowledge_base_id == instance.id,
                KnowledgeDocument.is_deleted.is_(True),
            )
            .values(
                is_deleted=False,
                deleted_at=None,
                delete_level=None,
                recycle_stage=None,
                promoted_to_global_at=None,
                updated_at=now,
            )
        )
        doc_ids_query = select(KnowledgeDocument.id).where(
            KnowledgeDocument.knowledge_base_id == instance.id,
        )
        await self.repo.db.execute(
            update(DocumentChunk)
            .where(
                DocumentChunk.document_id.in_(doc_ids_query),
                DocumentChunk.is_deleted.is_(True),
            )
            .values(
                is_deleted=False,
                deleted_at=None,
                delete_level=None,
                recycle_stage=None,
                promoted_to_global_at=None,
                updated_at=now,
            )
        )
        await self.repo.update_statistics(instance.id)
        from app.ai.rag.retriever import HybridRetriever
        await HybridRetriever.invalidate_kb_cache(instance.id)

    async def _check_name_unique(
        self,
        name: str,
        owner_tenant_id: int | None,
        scope: str,
        exclude_id: int | None = None,
    ) -> KnowledgeBase | None:
        """检查同 scope + owner_tenant_id 下名称是否重复 / Check name unique."""
        conditions = [
            KnowledgeBase.name == name,
            KnowledgeBase.scope == scope,
            KnowledgeBase.is_deleted.is_(False),
        ]
        if owner_tenant_id is not None:
            conditions.append(KnowledgeBase.owner_tenant_id == owner_tenant_id)
        else:
            conditions.append(KnowledgeBase.owner_tenant_id.is_(None))
        if exclude_id is not None:
            conditions.append(KnowledgeBase.id != exclude_id)

        stmt = select(KnowledgeBase).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


__all__ = [
    "KnowledgeBaseService",
    "KnowledgeDocumentService",
    "DocumentChunkService",
    "AdminKnowledgeBaseService",
]
