"""
Knowledge base service facades.
"""

from __future__ import annotations

from typing import Any

from app.core.base_service import GlobalService, TenantService
from app.core.i18n import _
from app.exceptions import BusinessException
from app.models.ai.document_chunk import DocumentChunk
from app.models.ai.knowledge_base import KnowledgeBase
from app.models.ai.knowledge_document import KnowledgeDocument
from app.repositories.ai.knowledge_base_repository import (
    AdminKnowledgeBaseRepository,
    DocumentChunkRepository,
    KnowledgeBaseRepository,
    KnowledgeDocumentRepository,
)
from app.services.ai.knowledge_base_command_service import (
    AdminKnowledgeBaseCommandService,
    KnowledgeBaseCommandService,
)
from app.services.ai.knowledge_base_query_service import KnowledgeBaseQueryService

_RETIRED_TENANT_KB_ALIAS_FIELDS = (
    "assigned_tenant_ids",
    "tenant_id",
)


def _reject_retired_tenant_kb_alias_fields(data: dict[str, Any]) -> None:
    for field in _RETIRED_TENANT_KB_ALIAS_FIELDS:
        if field in data:
            raise BusinessException(
                message=_("agent.error.rejected_legacy_field").format(field=field)
            )


class KnowledgeBaseService(TenantService[KnowledgeBase, KnowledgeBaseRepository]):
    """Tenant knowledge-base facade over command/query helpers."""

    model = KnowledgeBase
    repository_class = KnowledgeBaseRepository

    async def _before_create(self, data: dict[str, Any]) -> None:
        _reject_retired_tenant_kb_alias_fields(data)
        await super()._before_create(data)
        await KnowledgeBaseCommandService.before_create(self, data)

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        _reject_retired_tenant_kb_alias_fields(data)
        await super()._before_update(id, data)
        await KnowledgeBaseCommandService.before_update(self, id, data)

    async def _before_delete(self, id: int) -> None:
        await super()._before_delete(id)
        await KnowledgeBaseCommandService.before_delete(self, id)

    async def promote_to_global(self, id: int) -> KnowledgeBase | None:
        return await KnowledgeBaseCommandService.promote_to_global(self, id)

    async def _after_restore(self, instance: KnowledgeBase) -> None:
        await KnowledgeBaseCommandService.after_restore(self, instance)

    async def get_kb_detail(self, kb_id: int) -> dict[str, Any]:
        return await KnowledgeBaseQueryService(self.repo).get_kb_detail(kb_id)

    async def list_selectable(self, *, limit: int = 500) -> list[KnowledgeBase]:
        return await self.repo.list_selectable(limit=limit)

    async def update_statistics(self, kb_id: int) -> None:
        await KnowledgeBaseCommandService.update_statistics(self, kb_id)

    async def check_kb_quota(self) -> None:
        await KnowledgeBaseCommandService.check_kb_quota(self)

    async def check_document_quota(self, kb_id: int) -> None:
        await KnowledgeBaseCommandService.check_document_quota(self, kb_id)

    async def reindex_knowledge_base(self, kb_id: int) -> int:
        return await KnowledgeBaseCommandService.reindex_knowledge_base(self, kb_id)


class KnowledgeDocumentService(
    TenantService[KnowledgeDocument, KnowledgeDocumentRepository]
):
    """Tenant knowledge-document facade."""

    model = KnowledgeDocument
    repository_class = KnowledgeDocumentRepository

    async def get_by_kb_and_hash(
        self,
        knowledge_base_id: int,
        file_hash: str,
    ) -> KnowledgeDocument | None:
        return await self.repo.get_by_kb_and_hash(knowledge_base_id, file_hash)

    async def update_status(
        self,
        doc_id: int,
        status: str,
        error_message: str | None = None,
        error_stage: str | None = None,
    ) -> None:
        await self.repo.update_status(doc_id, status, error_message, error_stage)


class DocumentChunkService(TenantService[DocumentChunk, DocumentChunkRepository]):
    """Tenant document-chunk facade."""

    model = DocumentChunk
    repository_class = DocumentChunkRepository

    async def delete_by_document(self, document_id: int) -> int:
        return await self.repo.delete_by_document(document_id)

    async def get_by_document(
        self,
        document_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> list[DocumentChunk]:
        return await self.repo.get_by_document(document_id, skip, limit)

    async def list_document_chunks(
        self,
        *,
        document_id: int,
        page: int,
        page_size: int,
    ) -> list[DocumentChunk]:
        return await self.get_by_document(
            document_id=document_id,
            skip=(page - 1) * page_size,
            limit=page_size,
        )


class AdminKnowledgeBaseService(
    GlobalService[KnowledgeBase, AdminKnowledgeBaseRepository]
):
    """Admin knowledge-base facade over command helpers."""

    model = KnowledgeBase
    repository_class = AdminKnowledgeBaseRepository

    def _prepare_admin_payload(
        self,
        data: dict[str, Any],
        *,
        existing: KnowledgeBase | None = None,
    ) -> tuple[dict[str, Any], list[int] | None]:
        return AdminKnowledgeBaseCommandService.prepare_admin_payload(
            self,
            data,
            existing=existing,
        )

    async def create_admin_knowledge_base(
        self,
        data: dict[str, Any],
    ) -> tuple[KnowledgeBase, list[int] | None]:
        return await AdminKnowledgeBaseCommandService.create_admin_knowledge_base(
            self,
            data,
        )

    async def update_admin_knowledge_base(
        self,
        id: int,
        data: dict[str, Any],
    ) -> tuple[KnowledgeBase, list[int] | None]:
        return await AdminKnowledgeBaseCommandService.update_admin_knowledge_base(
            self,
            id,
            data,
        )

    async def _before_create(self, data: dict[str, Any]) -> None:
        await super()._before_create(data)
        await AdminKnowledgeBaseCommandService.before_create(self, data)

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        await super()._before_update(id, data)
        await AdminKnowledgeBaseCommandService.before_update(self, id, data)

    async def _before_delete(self, id: int) -> None:
        await super()._before_delete(id)
        await AdminKnowledgeBaseCommandService.before_delete(self, id)

    async def promote_to_global(self, id: int) -> KnowledgeBase | None:
        return await AdminKnowledgeBaseCommandService.promote_to_global(self, id)

    async def _after_restore(self, instance: KnowledgeBase) -> None:
        await AdminKnowledgeBaseCommandService.after_restore(self, instance)

    async def _check_name_unique(
        self,
        name: str,
        owner_tenant_id: int | None,
        scope: str,
        exclude_id: int | None = None,
    ) -> KnowledgeBase | None:
        return await AdminKnowledgeBaseCommandService.check_name_unique(
            self,
            name,
            owner_tenant_id,
            scope,
            exclude_id=exclude_id,
        )


__all__ = [
    "KnowledgeBaseService",
    "KnowledgeDocumentService",
    "DocumentChunkService",
    "AdminKnowledgeBaseService",
]
