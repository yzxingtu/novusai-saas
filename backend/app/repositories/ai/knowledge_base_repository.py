"""
知识库 Repository / Knowledge Base Repository

提供知识库、文档、分块的数据访问层
Provides knowledge base, document, chunk data access layer.
"""

from sqlalchemy import and_, func, or_, select, update

from app.core.base_repository import BaseRepository, TenantRepository
from app.enums.common import ResourceScopeEnum
from app.models.ai.document_chunk import DocumentChunk
from app.models.ai.knowledge_base import KnowledgeBase
from app.models.ai.knowledge_document import KnowledgeDocument
from app.repositories.system.resource_tenant_assignment_repository import (
    assigned_resource_ids_subquery,
)
from app.schemas.common.query import FilterRule, QuerySpec

_ASSIGNED_SCOPES = (
    ResourceScopeEnum.SELECTED_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
)


def _kb_visible_condition(tenant_id: int | None):
    """当前企业可见的知识库条件 / KB visible to tenant.

    When tenant_id is None (platform/admin context), all platform-owned KBs
    are visible regardless of scope — including admin_only KBs.
    """
    # Platform/admin context: all platform-owned KBs are visible
    if tenant_id is None:
        return KnowledgeBase.owner_tenant_id.is_(None)

    assigned_subq = assigned_resource_ids_subquery("knowledge_base", tenant_id)
    tenant_owned_visible = and_(
        KnowledgeBase.owner_tenant_id == tenant_id,
        KnowledgeBase.scope == ResourceScopeEnum.ALL_TENANTS.value,
    )
    platform_visible = and_(
        KnowledgeBase.owner_tenant_id.is_(None),
        KnowledgeBase.scope.in_(
            [
                ResourceScopeEnum.ALL_TENANTS.value,
                ResourceScopeEnum.GLOBAL_SHARED.value,
            ]
        ),
    )
    assigned_visible = and_(
        KnowledgeBase.owner_tenant_id.is_(None),
        KnowledgeBase.scope.in_(_ASSIGNED_SCOPES),
        KnowledgeBase.id.in_(assigned_subq),
    )
    return or_(
        tenant_owned_visible,
        platform_visible,
        assigned_visible,
    )


def _kb_child_visible_condition(tenant_id: int | None, child_tenant_column):
    """当前企业可读的 KB 子资源条件 / KB child rows readable by current tenant.

    When tenant_id is None (platform/admin context), child rows are visible
    if their tenant_id matches the parent KB's owner_tenant_id.
    This correctly covers:
    - admin_only KB (both NULL) ✅
    - global_shared KB (both NULL) ✅
    - all_tenants KB owned by tenant (both = tenant_id) ✅
    """
    if tenant_id is None:
        # Platform context: child tenant must match KB owner (NULL-safe comparison)
        # SQL "NULL = NULL" returns NULL, so use IS NOT DISTINCT FROM instead
        return child_tenant_column.isnot_distinct_from(KnowledgeBase.owner_tenant_id)

    return or_(
        and_(
            KnowledgeBase.owner_tenant_id == tenant_id,
            child_tenant_column == tenant_id,
        ),
        and_(
            KnowledgeBase.owner_tenant_id.is_(None),
            child_tenant_column.is_(None),
        ),
    )


class KnowledgeBaseRepository(TenantRepository[KnowledgeBase]):
    """
    企业级知识库 Repository / Tenant-scoped knowledge base repository.
    """

    model = KnowledgeBase

    async def get_by_id(
        self,
        id: int,
        include_deleted: bool = False,
    ) -> KnowledgeBase | None:
        """根据 ID 获取当前企业可访问的知识库 / Get KB by ID if visible to current tenant."""
        instance = await BaseRepository.get_by_id(self, id, include_deleted)
        if not instance:
            return None
        chk = await self.db.execute(
            select(KnowledgeBase.id).where(
                KnowledgeBase.id == id,
                _kb_visible_condition(self.tenant_id),
            )
        )
        return instance if chk.scalar_one_or_none() is not None else None

    async def query_list(
        self,
        spec: QuerySpec,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[KnowledgeBase], int]:
        """企业级知识库列表 / Tenant KB list with visibility rules."""
        allowed_fields = self.get_allowed_fields(scope)
        all_fields = self.get_allowed_fields(None)

        query = select(self.model)

        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        query = query.where(_kb_visible_condition(self.tenant_id))

        extra_forced = [
            f
            for f in (forced_filters or [])
            if f.field not in ("tenant_id", "owner_tenant_id")
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
        """同企业归属下按名称查找 / Find KB by name under owning tenant."""
        conditions = [
            KnowledgeBase.owner_tenant_id == self.tenant_id,
            KnowledgeBase.name == name,
            KnowledgeBase.is_deleted.is_(False),
        ]
        if exclude_id is not None:
            conditions.append(KnowledgeBase.id != exclude_id)

        stmt = select(KnowledgeBase).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def filter_accessible_ids(self, kb_ids: list[int]) -> set[int]:
        """批量过滤当前企业仍可访问的知识库 ID / Filter KB IDs still visible to current tenant."""
        unique_ids = {int(kb_id) for kb_id in kb_ids}
        if not unique_ids:
            return set()

        stmt = select(KnowledgeBase.id).where(
            KnowledgeBase.id.in_(unique_ids),
            KnowledgeBase.is_deleted.is_(False),
            _kb_visible_condition(self.tenant_id),
        )
        result = await self.db.execute(stmt)
        return {int(kb_id) for kb_id in result.scalars().all()}

    async def list_selectable(self, *, limit: int = 500) -> list[KnowledgeBase]:
        """获取当前企业可选择的知识库 / List KB rows selectable by the current tenant."""
        stmt = (
            select(KnowledgeBase)
            .where(
                KnowledgeBase.is_deleted.is_(False),
                _kb_visible_condition(self.tenant_id),
            )
            .order_by(KnowledgeBase.name.asc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_statistics(
        self,
        kb_id: int,
    ) -> None:
        """重新计算并更新知识库统计 / Recompute KB statistics."""
        doc_stmt = select(
            func.count(KnowledgeDocument.id),
            func.coalesce(func.sum(KnowledgeDocument.file_size), 0),
        ).where(
            and_(
                KnowledgeDocument.knowledge_base_id == kb_id,
                KnowledgeDocument.is_deleted.is_(False),
            )
        )
        doc_result = await self.db.execute(doc_stmt)
        doc_count, total_size = doc_result.one()

        chunk_stmt = select(func.count(DocumentChunk.id)).where(
            and_(
                DocumentChunk.knowledge_base_id == kb_id,
                DocumentChunk.is_deleted.is_(False),
            )
        )
        chunk_result = await self.db.execute(chunk_stmt)
        total_chunks = chunk_result.scalar() or 0

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
        """统计当前企业自有知识库数量 / Count KB rows owned by current tenant."""
        return await self.count()


class AdminKnowledgeBaseRepository(BaseRepository[KnowledgeBase]):
    """管理端知识库 Repository / Admin KB repository."""

    model = KnowledgeBase

    async def filter_accessible_ids(self, kb_ids: list[int]) -> set[int]:
        """批量过滤管理端仍存在的知识库 ID / Filter KB IDs still present for admin."""
        unique_ids = {int(kb_id) for kb_id in kb_ids}
        if not unique_ids:
            return set()

        stmt = select(KnowledgeBase.id).where(
            KnowledgeBase.id.in_(unique_ids),
            KnowledgeBase.is_deleted.is_(False),
        )
        result = await self.db.execute(stmt)
        return {int(kb_id) for kb_id in result.scalars().all()}

    async def update_statistics(
        self,
        kb_id: int,
    ) -> None:
        """重新计算并更新知识库统计 / Recompute KB statistics."""
        doc_stmt = select(
            func.count(KnowledgeDocument.id),
            func.coalesce(func.sum(KnowledgeDocument.file_size), 0),
        ).where(
            and_(
                KnowledgeDocument.knowledge_base_id == kb_id,
                KnowledgeDocument.is_deleted.is_(False),
            )
        )
        doc_result = await self.db.execute(doc_stmt)
        doc_count, total_size = doc_result.one()

        chunk_stmt = select(func.count(DocumentChunk.id)).where(
            and_(
                DocumentChunk.knowledge_base_id == kb_id,
                DocumentChunk.is_deleted.is_(False),
            )
        )
        chunk_result = await self.db.execute(chunk_stmt)
        total_chunks = chunk_result.scalar() or 0

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


class KnowledgeDocumentRepository(TenantRepository[KnowledgeDocument]):
    """企业级知识文档 Repository / Tenant-scoped knowledge document repository."""

    model = KnowledgeDocument

    async def get_by_id(
        self,
        id: int,
        include_deleted: bool = False,
    ) -> KnowledgeDocument | None:
        """按当前企业可见 KB 边界读取文档 / Read a document through current tenant KB visibility."""
        stmt = (
            select(KnowledgeDocument)
            .join(
                KnowledgeBase, KnowledgeBase.id == KnowledgeDocument.knowledge_base_id
            )
            .where(
                KnowledgeDocument.id == id,
                KnowledgeBase.is_deleted.is_(False),
                _kb_visible_condition(self.tenant_id),
                _kb_child_visible_condition(
                    self.tenant_id,
                    KnowledgeDocument.tenant_id,
                ),
            )
        )
        if not include_deleted:
            stmt = stmt.where(KnowledgeDocument.is_deleted.is_(False))

        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def query_list(
        self,
        spec: QuerySpec,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[KnowledgeDocument], int]:
        """按 KB 可见性列出文档 / List documents through KB visibility rules."""
        allowed_fields = self.get_allowed_fields(scope)
        all_fields = self.get_allowed_fields(None)

        query = select(KnowledgeDocument).join(
            KnowledgeBase,
            KnowledgeBase.id == KnowledgeDocument.knowledge_base_id,
        )

        if not include_deleted:
            query = query.where(KnowledgeDocument.is_deleted.is_(False))

        query = query.where(
            KnowledgeBase.is_deleted.is_(False),
            _kb_visible_condition(self.tenant_id),
            _kb_child_visible_condition(self.tenant_id, KnowledgeDocument.tenant_id),
        )

        extra_forced = [f for f in (forced_filters or []) if f.field != "tenant_id"]
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

    async def get_by_kb_and_hash(
        self,
        knowledge_base_id: int,
        file_hash: str,
    ) -> KnowledgeDocument | None:
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
    """企业级文档分块 Repository / Tenant-scoped document chunk repository."""

    model = DocumentChunk

    async def delete_by_document(
        self,
        document_id: int,
        soft: bool = True,
    ) -> int:
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
        stmt = (
            select(DocumentChunk)
            .join(KnowledgeDocument, KnowledgeDocument.id == DocumentChunk.document_id)
            .join(
                KnowledgeBase, KnowledgeBase.id == KnowledgeDocument.knowledge_base_id
            )
            .where(
                and_(
                    DocumentChunk.document_id == document_id,
                    DocumentChunk.knowledge_base_id
                    == KnowledgeDocument.knowledge_base_id,
                    DocumentChunk.is_deleted.is_(False),
                    KnowledgeDocument.is_deleted.is_(False),
                    KnowledgeBase.is_deleted.is_(False),
                    _kb_visible_condition(self.tenant_id),
                    _kb_child_visible_condition(
                        self.tenant_id,
                        KnowledgeDocument.tenant_id,
                    ),
                    _kb_child_visible_condition(
                        self.tenant_id,
                        DocumentChunk.tenant_id,
                    ),
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
