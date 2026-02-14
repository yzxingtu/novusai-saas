"""
知识库 Service

提供知识库的创建、更新、删除等业务逻辑
"""

from typing import Any

from datetime import datetime

from sqlalchemy import and_, select, update

from app.repositories.ai.knowledge_base_repository import (
    KnowledgeBaseRepository,
    AdminKnowledgeBaseRepository,
    KnowledgeDocumentRepository,
    DocumentChunkRepository,
)
from app.models.ai.knowledge_base import KnowledgeBase
from app.models.ai.knowledge_document import KnowledgeDocument
from app.models.ai.document_chunk import DocumentChunk
from app.core.base_service import TenantService, GlobalService
from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException, NotFoundException

logger = LogManager.get_logger("ai.knowledge_base_service")


# 默认知识库配额
DEFAULT_MAX_KNOWLEDGE_BASES = 20
DEFAULT_MAX_DOCUMENTS_PER_KB = 500


class KnowledgeBaseService(TenantService[KnowledgeBase, KnowledgeBaseRepository]):
    """
    租户级知识库 Service

    提供知识库的创建、更新、删除、统计更新、配额检查等业务逻辑
    """

    model = KnowledgeBase
    repository_class = KnowledgeBaseRepository

    async def _before_create(self, data: dict[str, Any]) -> None:
        """创建前校验：名称唯一性 + 配额检查"""
        await super()._before_create(data)

        # 配额检查
        await self.check_kb_quota()

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name(name)
            if existing:
                raise BusinessException(message=_("knowledge_base.error.name_exists"))

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        """更新前校验：名称唯一性"""
        await super()._before_update(id, data)

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name(name, exclude_id=id)
            if existing:
                raise BusinessException(message=_("knowledge_base.error.name_exists"))

    async def _before_delete(self, id: int) -> None:
        """删除前：级联软删除文档和分块"""
        await super()._before_delete(id)

        level = self._default_delete_level
        now = datetime.utcnow()
        # 级联软删除文档分块
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
            .values(is_deleted=True, deleted_at=now, delete_level=level, updated_at=now)
        )
        # 级联软删除文档
        await self.repo.db.execute(
            update(KnowledgeDocument)
            .where(
                KnowledgeDocument.knowledge_base_id == id,
                KnowledgeDocument.is_deleted.is_(False),
            )
            .values(is_deleted=True, deleted_at=now, delete_level=level, updated_at=now)
        )

    async def escalate_delete(self, id: int) -> KnowledgeBase | None:
        """升级删除层级，级联升级文档和分块"""
        instance = await self.repo.escalate_delete_by_id(id)
        if instance is None:
            return None

        now = datetime.utcnow()
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
            .values(delete_level="admin", deleted_at=now, updated_at=now)
        )
        await self.repo.db.execute(
            update(KnowledgeDocument)
            .where(
                KnowledgeDocument.knowledge_base_id == id,
                KnowledgeDocument.is_deleted.is_(True),
            )
            .values(delete_level="admin", deleted_at=now, updated_at=now)
        )
        return instance

    async def _after_restore(self, instance: KnowledgeBase) -> None:
        """恢复后：级联恢复文档和分块"""
        now = datetime.utcnow()
        # 级联恢复文档
        await self.repo.db.execute(
            update(KnowledgeDocument)
            .where(
                KnowledgeDocument.knowledge_base_id == instance.id,
                KnowledgeDocument.is_deleted.is_(True),
            )
            .values(is_deleted=False, deleted_at=None, delete_level=None, updated_at=now)
        )
        # 级联恢复文档分块
        doc_ids_query = select(KnowledgeDocument.id).where(
            KnowledgeDocument.knowledge_base_id == instance.id,
        )
        await self.repo.db.execute(
            update(DocumentChunk)
            .where(
                DocumentChunk.document_id.in_(doc_ids_query),
                DocumentChunk.is_deleted.is_(True),
            )
            .values(is_deleted=False, deleted_at=None, delete_level=None, updated_at=now)
        )

    async def get_kb_detail(self, kb_id: int) -> dict[str, Any]:
        """
        获取知识库详情（含关联 Embedding 模型信息）

        Args:
            kb_id: 知识库 ID

        Returns:
            包含模型名称的知识库字典
        """
        kb = await self.repo.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message=_("knowledge_base.error.not_found"))

        result = kb.to_dict()
        result["embedding_model_name"] = None

        try:
            model_obj = getattr(kb, "embedding_model", None)
            if model_obj is not None:
                result["embedding_model_name"] = model_obj.name
        except (AttributeError, Exception):
            pass

        return result

    async def update_statistics(self, kb_id: int) -> None:
        """
        重新计算知识库统计

        Args:
            kb_id: 知识库 ID
        """
        await self.repo.update_statistics(kb_id)

    async def check_kb_quota(self) -> None:
        """检查租户知识库数量配额"""
        count = await self.repo.count_by_tenant()
        if count >= DEFAULT_MAX_KNOWLEDGE_BASES:
            raise BusinessException(
                message=_("knowledge_base.error.quota_exceeded"),
            )

    async def check_document_quota(self, kb_id: int) -> None:
        """检查知识库文档数量配额"""
        kb = await self.repo.get_by_id(kb_id)
        if kb and kb.document_count >= DEFAULT_MAX_DOCUMENTS_PER_KB:
            raise BusinessException(
                message=_("knowledge_base.error.document_limit_exceeded"),
            )

    async def reindex_knowledge_base(self, kb_id: int) -> int:
        """
        重新向量化知识库所有文档

        删除所有现有 chunks，重新触发 process_document

        Args:
            kb_id: 知识库 ID

        Returns:
            触发的文档数量
        """
        from app.enums.knowledge_base import DocumentStatusEnum

        kb = await self.repo.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message=_("knowledge_base.error.not_found"))

        # 查询所有未删除文档
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

        # 重置文档状态并触发重新处理
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
            "Reindex triggered: kb=%d, docs=%d",
            kb_id, count,
        )

        return count


class KnowledgeDocumentService(TenantService[KnowledgeDocument, KnowledgeDocumentRepository]):
    """
    租户级知识文档 Service
    """

    model = KnowledgeDocument
    repository_class = KnowledgeDocumentRepository

    async def get_by_kb_and_hash(
        self,
        knowledge_base_id: int,
        file_hash: str,
    ) -> KnowledgeDocument | None:
        """检查文件是否已存在（去重）"""
        return await self.repo.get_by_kb_and_hash(knowledge_base_id, file_hash)

    async def update_status(
        self,
        doc_id: int,
        status: str,
        error_message: str | None = None,
        error_stage: str | None = None,
    ) -> None:
        """更新文档处理状态"""
        await self.repo.update_status(doc_id, status, error_message, error_stage)


class DocumentChunkService(TenantService[DocumentChunk, DocumentChunkRepository]):
    """
    租户级文档分块 Service
    """

    model = DocumentChunk
    repository_class = DocumentChunkRepository

    async def delete_by_document(self, document_id: int) -> int:
        """删除指定文档的所有分块"""
        return await self.repo.delete_by_document(document_id)

    async def get_by_document(
        self,
        document_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> list[DocumentChunk]:
        """获取指定文档的分块列表"""
        return await self.repo.get_by_document(document_id, skip, limit)


class AdminKnowledgeBaseService(GlobalService[KnowledgeBase, AdminKnowledgeBaseRepository]):
    """
    管理端知识库 Service

    无租户隔离，供平台管理端全局查询和 CRUD 使用
    """

    model = KnowledgeBase
    repository_class = AdminKnowledgeBaseRepository

    async def _before_create(self, data: dict[str, Any]) -> None:
        """创建前校验：scope + tenant_id 一致性、名称唯一性"""
        await super()._before_create(data)

        from app.enums.common import ResourceScopeEnum

        scope = data.get("scope", ResourceScopeEnum.TENANT.value)
        tenant_id = data.get("tenant_id")

        if scope == ResourceScopeEnum.TENANT.value:
            if not tenant_id:
                raise BusinessException(
                    message=_("knowledge_base.error.tenant_id_required"),
                )
        else:
            data["tenant_id"] = None

        # 名称唯一性（同 scope + tenant_id 下）
        name = data.get("name")
        if name:
            existing = await self._check_name_unique(name, tenant_id=data.get("tenant_id"), scope=scope)
            if existing:
                raise BusinessException(message=_("knowledge_base.error.name_exists"))

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        """更新前校验：scope 变更时的一致性、名称唯一性"""
        await super()._before_update(id, data)

        from app.enums.common import ResourceScopeEnum

        kb = await self.repo.get_by_id(id)
        if not kb:
            raise NotFoundException(message=_("knowledge_base.error.not_found"))

        scope = data.get("scope", kb.scope)
        tenant_id = data.get("tenant_id", kb.tenant_id)

        if scope == ResourceScopeEnum.TENANT.value:
            if not tenant_id:
                raise BusinessException(
                    message=_("knowledge_base.error.tenant_id_required"),
                )
        else:
            data["tenant_id"] = None
            tenant_id = None

        name = data.get("name")
        if name:
            existing = await self._check_name_unique(name, tenant_id=tenant_id, scope=scope, exclude_id=id)
            if existing:
                raise BusinessException(message=_("knowledge_base.error.name_exists"))

    async def _before_delete(self, id: int) -> None:
        """删除前：级联软删除文档和分块"""
        await super()._before_delete(id)

        level = self._default_delete_level
        now = datetime.utcnow()
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
            .values(is_deleted=True, deleted_at=now, delete_level=level, updated_at=now)
        )
        await self.repo.db.execute(
            update(KnowledgeDocument)
            .where(
                KnowledgeDocument.knowledge_base_id == id,
                KnowledgeDocument.is_deleted.is_(False),
            )
            .values(is_deleted=True, deleted_at=now, delete_level=level, updated_at=now)
        )

    async def escalate_delete(self, id: int) -> KnowledgeBase | None:
        """升级删除层级，级联升级文档和分块"""
        instance = await self.repo.escalate_delete_by_id(id)
        if instance is None:
            return None

        now = datetime.utcnow()
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
            .values(delete_level="admin", deleted_at=now, updated_at=now)
        )
        await self.repo.db.execute(
            update(KnowledgeDocument)
            .where(
                KnowledgeDocument.knowledge_base_id == id,
                KnowledgeDocument.is_deleted.is_(True),
            )
            .values(delete_level="admin", deleted_at=now, updated_at=now)
        )
        return instance

    async def _after_restore(self, instance: KnowledgeBase) -> None:
        """恢复后：级联恢复文档和分块"""
        now = datetime.utcnow()
        await self.repo.db.execute(
            update(KnowledgeDocument)
            .where(
                KnowledgeDocument.knowledge_base_id == instance.id,
                KnowledgeDocument.is_deleted.is_(True),
            )
            .values(is_deleted=False, deleted_at=None, delete_level=None, updated_at=now)
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
            .values(is_deleted=False, deleted_at=None, delete_level=None, updated_at=now)
        )

    async def _check_name_unique(
        self,
        name: str,
        tenant_id: int | None,
        scope: str,
        exclude_id: int | None = None,
    ) -> KnowledgeBase | None:
        """检查同 scope+tenant_id 下名称是否重复"""
        conditions = [
            KnowledgeBase.name == name,
            KnowledgeBase.scope == scope,
            KnowledgeBase.is_deleted.is_(False),
        ]
        if tenant_id is not None:
            conditions.append(KnowledgeBase.tenant_id == tenant_id)
        else:
            conditions.append(KnowledgeBase.tenant_id.is_(None))
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
