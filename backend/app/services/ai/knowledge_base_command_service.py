"""
Command helpers for knowledge base services.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, select

from app.core.base_model import utc_now
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.common import ResourceScopeEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.knowledge_base import KnowledgeBase
from app.models.ai.knowledge_document import KnowledgeDocument
from app.services.ai.knowledge_base_support import (
    DEFAULT_MAX_DOCUMENTS_PER_KB,
    DEFAULT_MAX_KNOWLEDGE_BASES,
    KB_SCOPES_NEEDING_ASSIGNMENT,
    cascade_promote_to_global,
    cascade_restore_documents,
    cascade_soft_delete_documents,
)

logger = LogManager.get_logger("ai.knowledge_base_service")


def _reject_unsupported_multimodal_model_config(data: dict[str, Any]) -> None:
    """Fail closed on audio/video KB model overrides until real ingest owners exist."""

    unsupported_fields = (
        "audio_model_id",
        "video_model_id",
    )
    if any(data.get(field) is not None for field in unsupported_fields):
        raise BusinessException(
            message=_("knowledge_base.error.multimodal_model_config_unavailable")
        )


class KnowledgeBaseCommandService:
    """Command operations extracted from KnowledgeBaseService."""

    @staticmethod
    async def before_create(service, data: dict[str, Any]) -> None:
        _reject_unsupported_multimodal_model_config(data)
        await KnowledgeBaseCommandService.check_kb_quota(service)

        name = data.get("name")
        if name:
            existing = await service.repo.get_by_name(name)
            if existing:
                raise BusinessException(message=_("knowledge_base.error.name_exists"))

    @staticmethod
    async def before_update(service, id: int, data: dict[str, Any]) -> None:
        _reject_unsupported_multimodal_model_config(data)
        kb = await service.repo.get_by_id(id)
        if not kb:
            raise NotFoundException(message=_("knowledge_base.error.not_found"))

        if kb.owner_tenant_id != service.repo.tenant_id:
            raise BusinessException(message=_("knowledge_base.error.readonly"))

        name = data.get("name")
        if name:
            existing = await service.repo.get_by_name(name, exclude_id=id)
            if existing:
                raise BusinessException(message=_("knowledge_base.error.name_exists"))

    @staticmethod
    async def before_delete(service, id: int) -> None:
        kb = await service.repo.get_by_id(id)
        if not kb:
            raise NotFoundException(message=_("knowledge_base.error.not_found"))

        if kb.owner_tenant_id != service.repo.tenant_id:
            raise BusinessException(message=_("knowledge_base.error.readonly"))

        now = utc_now()
        await cascade_soft_delete_documents(
            service.repo.db,
            knowledge_base_id=id,
            delete_level=service._default_delete_level,
            now=now,
        )

    @staticmethod
    async def promote_to_global(service, id: int) -> KnowledgeBase | None:
        instance = await service.repo.promote_to_global_by_id(
            id,
            delete_level=service._default_delete_level,
        )
        if instance is None:
            return None

        now = utc_now()
        await cascade_promote_to_global(service.repo.db, knowledge_base_id=id, now=now)
        return instance

    @staticmethod
    async def after_restore(service, instance: KnowledgeBase) -> None:
        now = utc_now()
        await cascade_restore_documents(
            service.repo.db,
            knowledge_base_id=instance.id,
            now=now,
        )
        await service.repo.update_statistics(instance.id)
        from app.ai.rag.retriever import HybridRetriever

        await HybridRetriever.invalidate_kb_cache(instance.id)

    @staticmethod
    async def update_statistics(service, kb_id: int) -> None:
        await service.repo.update_statistics(kb_id)

    @staticmethod
    async def check_kb_quota(service) -> None:
        count = await service.repo.count_by_tenant()
        if count >= DEFAULT_MAX_KNOWLEDGE_BASES:
            raise BusinessException(
                message=_("knowledge_base.error.quota_exceeded"),
            )

    @staticmethod
    async def check_document_quota(service, kb_id: int) -> None:
        kb = await service.repo.get_by_id(kb_id)
        if kb and kb.document_count >= DEFAULT_MAX_DOCUMENTS_PER_KB:
            raise BusinessException(
                message=_("knowledge_base.error.document_limit_exceeded"),
            )

    @staticmethod
    async def reindex_knowledge_base(service, kb_id: int) -> int:
        from app.enums.knowledge_base import DocumentStatusEnum

        kb = await service.repo.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message=_("knowledge_base.error.not_found"))

        stmt = select(KnowledgeDocument).where(
            and_(
                KnowledgeDocument.knowledge_base_id == kb_id,
                KnowledgeDocument.tenant_id == service.repo.tenant_id,
                KnowledgeDocument.is_deleted.is_(False),
            )
        )
        result = await service.db.execute(stmt)
        docs = list(result.scalars().all())

        if not docs:
            return 0

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

        await service.db.commit()

        for doc in docs:
            process_document.delay(
                tenant_id=service.repo.tenant_id,
                document_id=doc.id,
            )

        logger.info(
            "Reindex triggered: kb={}, docs={}",
            kb_id,
            count,
        )

        return count


class AdminKnowledgeBaseCommandService:
    """Command operations extracted from AdminKnowledgeBaseService."""

    @staticmethod
    def prepare_admin_payload(
        _service,
        data: dict[str, Any],
        *,
        existing: KnowledgeBase | None = None,
    ) -> tuple[dict[str, Any], list[int] | None]:
        payload = dict(data)
        payload.pop("visibility", None)

        tenant_ids = payload.pop("tenant_ids", None)
        assigned_tenant_ids = payload.pop("assigned_tenant_ids", None)
        if tenant_ids is None:
            tenant_ids = assigned_tenant_ids

        normalized_tenant_ids: list[int] | None = None
        if tenant_ids is not None:
            normalized_tenant_ids = [int(tid) for tid in tenant_ids]

        incoming_tenant_id = payload.pop("tenant_id", None)
        if incoming_tenant_id is not None and payload.get("owner_tenant_id") is None:
            payload["owner_tenant_id"] = incoming_tenant_id

        scope = payload.get("scope", existing.scope if existing else None)
        if scope is None:
            scope = ResourceScopeEnum.GLOBAL_SHARED.value
            payload["scope"] = scope

        if scope in KB_SCOPES_NEEDING_ASSIGNMENT:
            if normalized_tenant_ids is not None and len(normalized_tenant_ids) == 0:
                raise BusinessException(
                    message=_("knowledge_base.error.binding_required")
                )
            if normalized_tenant_ids is None and (
                existing is None or existing.scope not in KB_SCOPES_NEEDING_ASSIGNMENT
            ):
                raise BusinessException(
                    message=_("knowledge_base.error.binding_required")
                )

        return payload, normalized_tenant_ids

    @staticmethod
    async def create_admin_knowledge_base(
        service,
        data: dict[str, Any],
    ) -> tuple[KnowledgeBase, list[int] | None]:
        payload, tenant_ids = AdminKnowledgeBaseCommandService.prepare_admin_payload(
            service,
            data,
        )
        kb = await service.create(payload)
        return kb, tenant_ids

    @staticmethod
    async def update_admin_knowledge_base(
        service,
        id: int,
        data: dict[str, Any],
    ) -> tuple[KnowledgeBase, list[int] | None]:
        kb = await service.get_by_id(id)
        if not kb:
            raise NotFoundException(message=_("knowledge_base.error.not_found"))

        payload, tenant_ids = AdminKnowledgeBaseCommandService.prepare_admin_payload(
            service,
            data,
            existing=kb,
        )
        updated = await service.update(id, payload)
        return updated, tenant_ids

    @staticmethod
    async def before_create(service, data: dict[str, Any]) -> None:
        _reject_unsupported_multimodal_model_config(data)
        scope = data.get("scope", ResourceScopeEnum.GLOBAL_SHARED.value)
        owner_tid = data.get("owner_tenant_id")
        name = data.get("name")
        if name:
            existing = await AdminKnowledgeBaseCommandService.check_name_unique(
                service,
                name,
                owner_tenant_id=owner_tid,
                scope=scope,
            )
            if existing:
                raise BusinessException(message=_("knowledge_base.error.name_exists"))

    @staticmethod
    async def before_update(service, id: int, data: dict[str, Any]) -> None:
        _reject_unsupported_multimodal_model_config(data)
        kb = await service.repo.get_by_id(id)
        if not kb:
            raise NotFoundException(message=_("knowledge_base.error.not_found"))

        scope = data.get("scope", kb.scope)
        owner_tid = data.get("owner_tenant_id", kb.owner_tenant_id)
        name = data.get("name")
        if name:
            existing = await AdminKnowledgeBaseCommandService.check_name_unique(
                service,
                name,
                owner_tenant_id=owner_tid,
                scope=scope,
                exclude_id=id,
            )
            if existing:
                raise BusinessException(message=_("knowledge_base.error.name_exists"))

    @staticmethod
    async def before_delete(service, id: int) -> None:
        now = utc_now()
        await cascade_soft_delete_documents(
            service.repo.db,
            knowledge_base_id=id,
            delete_level=service._default_delete_level,
            now=now,
        )

        from app.repositories.system.resource_tenant_assignment_repository import (
            ResourceTenantAssignmentRepository,
        )

        rta_repo = ResourceTenantAssignmentRepository(service.db)
        await rta_repo.delete_all_for_resource("knowledge_base", id)

    @staticmethod
    async def promote_to_global(service, id: int) -> KnowledgeBase | None:
        instance = await service.repo.promote_to_global_by_id(
            id,
            delete_level=service._default_delete_level,
        )
        if instance is None:
            return None

        now = utc_now()
        await cascade_promote_to_global(service.repo.db, knowledge_base_id=id, now=now)
        return instance

    @staticmethod
    async def after_restore(service, instance: KnowledgeBase) -> None:
        now = utc_now()
        await cascade_restore_documents(
            service.repo.db,
            knowledge_base_id=instance.id,
            now=now,
        )
        await service.repo.update_statistics(instance.id)
        from app.ai.rag.retriever import HybridRetriever

        await HybridRetriever.invalidate_kb_cache(instance.id)

    @staticmethod
    async def check_name_unique(
        service,
        name: str,
        owner_tenant_id: int | None,
        scope: str,
        exclude_id: int | None = None,
    ) -> KnowledgeBase | None:
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
        result = await service.db.execute(stmt)
        return result.scalar_one_or_none()


__all__ = ["KnowledgeBaseCommandService", "AdminKnowledgeBaseCommandService"]
