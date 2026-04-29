"""
Shared helpers for knowledge base services.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update

from app.enums.common import RecycleStageEnum, ResourceScopeEnum
from app.models.ai.document_chunk import DocumentChunk
from app.models.ai.knowledge_document import KnowledgeDocument

DEFAULT_MAX_KNOWLEDGE_BASES = 20
DEFAULT_MAX_DOCUMENTS_PER_KB = 500
KB_PLATFORM_OWNER_SCOPES = (
    ResourceScopeEnum.GLOBAL_SHARED.value,
    ResourceScopeEnum.ADMIN_ONLY.value,
    ResourceScopeEnum.ALL_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
    ResourceScopeEnum.SELECTED_TENANTS.value,
)
KB_TENANT_OWNER_SCOPES = (ResourceScopeEnum.ALL_TENANTS.value,)
KB_SCOPES_NEEDING_ASSIGNMENT = (
    ResourceScopeEnum.SELECTED_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
)


def _document_ids_query(knowledge_base_id: int, *, deleted: bool) -> Any:
    return select(KnowledgeDocument.id).where(
        KnowledgeDocument.knowledge_base_id == knowledge_base_id,
        KnowledgeDocument.is_deleted.is_(deleted),
    )


async def cascade_soft_delete_documents(
    db,
    *,
    knowledge_base_id: int,
    delete_level: int,
    now,
) -> None:
    doc_ids_query = _document_ids_query(knowledge_base_id, deleted=False)
    await db.execute(
        update(DocumentChunk)
        .where(
            DocumentChunk.document_id.in_(doc_ids_query),
            DocumentChunk.is_deleted.is_(False),
        )
        .values(
            is_deleted=True,
            deleted_at=now,
            delete_level=delete_level,
            recycle_stage=RecycleStageEnum.MODULE.value,
            promoted_to_global_at=None,
            updated_at=now,
        )
    )
    await db.execute(
        update(KnowledgeDocument)
        .where(
            KnowledgeDocument.knowledge_base_id == knowledge_base_id,
            KnowledgeDocument.is_deleted.is_(False),
        )
        .values(
            is_deleted=True,
            deleted_at=now,
            delete_level=delete_level,
            recycle_stage=RecycleStageEnum.MODULE.value,
            promoted_to_global_at=None,
            updated_at=now,
        )
    )


async def cascade_promote_to_global(
    db,
    *,
    knowledge_base_id: int,
    now,
) -> None:
    doc_ids_query = _document_ids_query(knowledge_base_id, deleted=True)
    await db.execute(
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
    await db.execute(
        update(KnowledgeDocument)
        .where(
            KnowledgeDocument.knowledge_base_id == knowledge_base_id,
            KnowledgeDocument.is_deleted.is_(True),
        )
        .values(
            recycle_stage=RecycleStageEnum.GLOBAL.value,
            promoted_to_global_at=now,
            updated_at=now,
        )
    )


async def cascade_restore_documents(
    db,
    *,
    knowledge_base_id: int,
    now,
) -> None:
    await db.execute(
        update(KnowledgeDocument)
        .where(
            KnowledgeDocument.knowledge_base_id == knowledge_base_id,
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
        KnowledgeDocument.knowledge_base_id == knowledge_base_id,
    )
    await db.execute(
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


def allowed_scopes_for_kb_owner(owner_tenant_id: int | None) -> tuple[str, ...]:
    """Return valid KB scopes for platform-owned vs tenant-owned rows."""
    if owner_tenant_id is None:
        return KB_PLATFORM_OWNER_SCOPES
    return KB_TENANT_OWNER_SCOPES


def is_valid_kb_scope_owner(
    *,
    scope: str,
    owner_tenant_id: int | None,
) -> bool:
    return scope in allowed_scopes_for_kb_owner(owner_tenant_id)


__all__ = [
    "DEFAULT_MAX_KNOWLEDGE_BASES",
    "DEFAULT_MAX_DOCUMENTS_PER_KB",
    "KB_PLATFORM_OWNER_SCOPES",
    "KB_SCOPES_NEEDING_ASSIGNMENT",
    "KB_TENANT_OWNER_SCOPES",
    "allowed_scopes_for_kb_owner",
    "cascade_soft_delete_documents",
    "cascade_promote_to_global",
    "cascade_restore_documents",
    "is_valid_kb_scope_owner",
]
