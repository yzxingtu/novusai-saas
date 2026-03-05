"""
知识库 Repository

提供知识库、文档、分块的数据访问层
"""

from sqlalchemy import and_, func, or_, select, update

from app.core.base_repository import BaseRepository, TenantRepository
from app.enums.common import ResourceScopeEnum
from app.enums.knowledge_base import KBVisibilityEnum
from app.models.ai.document_chunk import DocumentChunk
from app.models.ai.knowledge_base import KnowledgeBase
from app.models.ai.knowledge_base_tenant_access import KnowledgeBaseTenantAccess
from app.models.ai.knowledge_document import KnowledgeDocument
from app.repositories.system.resource_tenant_assignment_repository import (
    assigned_resource_ids_subquery,
)
from app.schemas.common.query import FilterRule, QuerySpec

_ASSIGNED_SCOPES = (
    ResourceScopeEnum.ASSIGNED_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_ASSIGNED.value,
)


class KnowledgeBaseRepository(TenantRepository[KnowledgeBase]):
    """
    租户级知识库 Repository

    提供基于租户隔离的知识库数据访问。
    查询时自动包含 scope=global 的全局知识库。
    """

    model = KnowledgeBase

    async def get_by_id(
        self,
        id: int,
        include_deleted: bool = False,
    ) -> KnowledgeBase | None:
        """
        根据 ID 获取知识库，检查可见性权限

        访问规则：
        - 自己租户的 KB → 允许
        - scope=global → 允许（全局知识库对所有租户可见）
        - visibility=all_tenants → 允许
        - visibility=assigned → 检查 KnowledgeBaseTenantAccess 关联
        - 其他 → 拒绝
        """
        instance = await BaseRepository.get_by_id(self, id, include_deleted)
        if not instance:
            return None
        # 自己租户的 KB
        if instance.tenant_id == self.tenant_id:
            return instance
        # 全局作用域的 KB（admin_and_all）
        if getattr(instance, "scope", None) == ResourceScopeEnum.ADMIN_AND_ALL.value:
            return instance
        # 平台创建的全局 KB（scope=all_tenants, tenant_id=null）
        if getattr(instance, "scope", None) == ResourceScopeEnum.ALL_TENANTS.value and instance.tenant_id is None:
            return instance
        # assigned_tenants / admin_and_assigned scope：检查 resource_tenant_assignments
        if getattr(instance, "scope", None) in _ASSIGNED_SCOPES:
            from app.repositories.system.resource_tenant_assignment_repository import (
                ResourceTenantAssignmentRepository,
            )
            repo = ResourceTenantAssignmentRepository(self.db)
            if await repo.check_assignment("knowledge_base", instance.id, self.tenant_id):
                return instance
            return None
        # 对所有租户可见
        if instance.visibility == KBVisibilityEnum.ALL_TENANTS.value:
            return instance
        # 指定租户可见（旧机制）：检查 KnowledgeBaseTenantAccess 关联表
        if instance.visibility == KBVisibilityEnum.ASSIGNED.value:
            access_stmt = select(KnowledgeBaseTenantAccess.id).where(
                KnowledgeBaseTenantAccess.knowledge_base_id == id,
                KnowledgeBaseTenantAccess.tenant_id == self.tenant_id,
                KnowledgeBaseTenantAccess.is_deleted.is_(False),
            ).limit(1)
            result = await self.db.execute(access_stmt)
            if result.scalar_one_or_none() is not None:
                return instance
        return None

    async def query_list(
        self,
        spec: QuerySpec,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[KnowledgeBase], int]:
        """
        租户级知识库列表查询

        自动注入条件：(tenant_id = X) OR (scope = 'admin_and_all')
        """
        allowed_fields = self.get_allowed_fields(scope)
        all_fields = self.get_allowed_fields(None)

        query = select(self.model)

        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        # 可见性过滤：自己的 KB + all_tenants + assigned(关联表)
        assigned_subq = (
            select(KnowledgeBaseTenantAccess.knowledge_base_id)
            .where(
                KnowledgeBaseTenantAccess.tenant_id == self.tenant_id,
                KnowledgeBaseTenantAccess.is_deleted.is_(False),
            )
        ).scalar_subquery()

        rta_subq = assigned_resource_ids_subquery("knowledge_base", self.tenant_id)
        query = query.where(
            or_(
                self.model.tenant_id == self.tenant_id,
                self.model.visibility == KBVisibilityEnum.ALL_TENANTS.value,
                and_(
                    self.model.visibility == KBVisibilityEnum.ASSIGNED.value,
                    self.model.id.in_(assigned_subq),
                ),
                # 全局共享 KB（admin_and_all）
                self.model.scope == ResourceScopeEnum.ADMIN_AND_ALL.value,
                # 平台创建的全局 KB（scope=all_tenants, tenant_id=null）
                and_(
                    self.model.scope == ResourceScopeEnum.ALL_TENANTS.value,
                    self.model.tenant_id.is_(None),
                ),
                # assigned_tenants / admin_and_assigned scope
                and_(
                    self.model.scope.in_(_ASSIGNED_SCOPES),
                    self.model.id.in_(rta_subq),
                ),
            )
        )

        # 应用额外的强制过滤（排除 tenant_id 强制规则）
        extra_forced = [
            f for f in (forced_filters or [])
            if f.field != "tenant_id"
        ]
        if extra_forced:
            query = self._apply_filters(query, extra_forced, all_fields)

        if spec.filters:
            query = self._apply_filters(query, spec.filters, allowed_fields)

        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        sortable_fields = self.get_sortable_fields()
        query = self._apply_sort(query, spec.sort, sortable_fields)
        query = query.offset(spec.offset).limit(spec.limit)

        result = await self.db.execute(query)
        items = list(result.scalars().all())
        return items, total

    async def get_by_name(
        self,
        name: str,
        exclude_id: int | None = None,
    ) -> KnowledgeBase | None:
        """
        按名称查找知识库（同租户内唯一性检查）

        Args:
            name: 知识库名称
            exclude_id: 排除的 ID（用于更新时排除自身）

        Returns:
            KnowledgeBase 实例或 None
        """
        conditions = [
            KnowledgeBase.tenant_id == self.tenant_id,
            KnowledgeBase.name == name,
            KnowledgeBase.is_deleted.is_(False),
        ]
        if exclude_id is not None:
            conditions.append(KnowledgeBase.id != exclude_id)

        stmt = select(KnowledgeBase).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_statistics(
        self,
        kb_id: int,
    ) -> None:
        """
        重新计算并更新知识库统计（文档数、分块数、总大小）

        Args:
            kb_id: 知识库 ID
        """
        # 统计文档数和总大小
        doc_stmt = (
            select(
                func.count(KnowledgeDocument.id),
                func.coalesce(func.sum(KnowledgeDocument.file_size), 0),
            )
            .where(
                and_(
                    KnowledgeDocument.knowledge_base_id == kb_id,
                    KnowledgeDocument.is_deleted.is_(False),
                )
            )
        )
        doc_result = await self.db.execute(doc_stmt)
        doc_count, total_size = doc_result.one()

        # 统计分块总数
        chunk_stmt = (
            select(func.count(DocumentChunk.id))
            .where(
                and_(
                    DocumentChunk.knowledge_base_id == kb_id,
                    DocumentChunk.is_deleted.is_(False),
                )
            )
        )
        chunk_result = await self.db.execute(chunk_stmt)
        total_chunks = chunk_result.scalar() or 0

        # 更新知识库统计
        update_stmt = (
            update(KnowledgeBase)
            .where(KnowledgeBase.id == kb_id)
            .values(
                document_count=doc_count,
                total_chunks=total_chunks,
                total_size_bytes=total_size,
            )
        )
        await self.db.execute(update_stmt)

    async def count_by_tenant(self) -> int:
        """统计当前租户的知识库总数"""
        return await self.count()


class AdminKnowledgeBaseRepository(BaseRepository[KnowledgeBase]):
    """
    管理端知识库 Repository

    无租户隔离，供平台管理端全局查询使用
    """

    model = KnowledgeBase


class KnowledgeDocumentRepository(TenantRepository[KnowledgeDocument]):
    """
    租户级知识文档 Repository
    """

    model = KnowledgeDocument

    async def get_by_kb_and_hash(
        self,
        knowledge_base_id: int,
        file_hash: str,
    ) -> KnowledgeDocument | None:
        """
        按知识库 ID 和文件哈希查找文档（去重检测）

        Args:
            knowledge_base_id: 知识库 ID
            file_hash: 文件 MD5 哈希

        Returns:
            KnowledgeDocument 实例或 None
        """
        stmt = select(KnowledgeDocument).where(
            and_(
                KnowledgeDocument.knowledge_base_id == knowledge_base_id,
                KnowledgeDocument.file_hash == file_hash,
                KnowledgeDocument.tenant_id == self.tenant_id,
                KnowledgeDocument.is_deleted.is_(False),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        doc_id: int,
        status: str,
        error_message: str | None = None,
        error_stage: str | None = None,
    ) -> None:
        """
        更新文档处理状态

        Args:
            doc_id: 文档 ID
            status: 新状态
            error_message: 错误信息（仅 error 状态时设置）
            error_stage: 错误阶段
        """
        values: dict = {"status": status}
        if error_message is not None:
            values["error_message"] = error_message
        if error_stage is not None:
            values["error_stage"] = error_stage

        stmt = (
            update(KnowledgeDocument)
            .where(KnowledgeDocument.id == doc_id)
            .values(**values)
        )
        await self.db.execute(stmt)


class DocumentChunkRepository(TenantRepository[DocumentChunk]):
    """
    租户级文档分块 Repository
    """

    model = DocumentChunk

    async def delete_by_document(
        self,
        document_id: int,
        soft: bool = True,
    ) -> int:
        """
        删除指定文档的所有分块

        Args:
            document_id: 文档 ID
            soft: 是否软删除

        Returns:
            删除的记录数量
        """
        if soft:
            stmt = (
                update(DocumentChunk)
                .where(
                    and_(
                        DocumentChunk.document_id == document_id,
                        DocumentChunk.tenant_id == self.tenant_id,
                        DocumentChunk.is_deleted.is_(False),
                    )
                )
                .values(is_deleted=True)
            )
        else:
            from sqlalchemy import delete as sa_delete
            stmt = sa_delete(DocumentChunk).where(
                and_(
                    DocumentChunk.document_id == document_id,
                    DocumentChunk.tenant_id == self.tenant_id,
                )
            )
        result = await self.db.execute(stmt)
        return result.rowcount

    async def get_by_document(
        self,
        document_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> list[DocumentChunk]:
        """
        获取指定文档的分块列表

        Args:
            document_id: 文档 ID
            skip: 跳过数量
            limit: 返回数量

        Returns:
            DocumentChunk 列表
        """
        stmt = (
            select(DocumentChunk)
            .where(
                and_(
                    DocumentChunk.document_id == document_id,
                    DocumentChunk.tenant_id == self.tenant_id,
                    DocumentChunk.is_deleted.is_(False),
                )
            )
            .order_by(DocumentChunk.chunk_index.asc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


__all__ = [
    "KnowledgeBaseRepository",
    "AdminKnowledgeBaseRepository",
    "KnowledgeDocumentRepository",
    "DocumentChunkRepository",
]
