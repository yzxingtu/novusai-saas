"""
Ephemeral document service / 临时资料文档服务
"""

from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Any

from app.core.base_model import utc_now
from app.core.base_service import TenantService
from app.enums.knowledge_base import (
    DocumentStatusEnum,
    DocumentTypeEnum,
    EphemeralDocScopeEnum,
    EphemeralDocStatusEnum,
)
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.ephemeral_document import EphemeralDocument
from app.models.ai.knowledge_document import KnowledgeDocument
from app.repositories.ai.ephemeral_document_repository import EphemeralDocumentRepository
from app.repositories.ai.knowledge_base_repository import AdminKnowledgeBaseRepository

_DEFAULT_TTL_SECONDS = {
    EphemeralDocScopeEnum.CONVERSATION_SCOPED.value: 24 * 60 * 60,
    EphemeralDocScopeEnum.AGENT_WORKSPACE_SCOPED.value: 7 * 24 * 60 * 60,
    EphemeralDocScopeEnum.TENANT_PRIVATE_SCRATCH.value: 7 * 24 * 60 * 60,
}
_MAX_TTL_SECONDS = 30 * 24 * 60 * 60


def _content_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


class EphemeralDocumentService(
    TenantService[EphemeralDocument, EphemeralDocumentRepository]
):
    model = EphemeralDocument
    repository_class = EphemeralDocumentRepository

    @staticmethod
    def build_scope_key(
        *,
        scope_type: str,
        conversation_id: int | None,
        agent_id: int | None,
        user_id: int | None,
    ) -> str:
        if scope_type == EphemeralDocScopeEnum.AGENT_WORKSPACE_SCOPED.value:
            return f"agent:{agent_id or 0}"
        if scope_type == EphemeralDocScopeEnum.TENANT_PRIVATE_SCRATCH.value:
            return f"user:{user_id or 0}"
        return f"conversation:{conversation_id or 0}"

    @classmethod
    def normalize_scope_type(cls, value: str | None) -> str:
        normalized = str(value or "").strip()
        if normalized in {
            EphemeralDocScopeEnum.CONVERSATION_SCOPED.value,
            EphemeralDocScopeEnum.AGENT_WORKSPACE_SCOPED.value,
            EphemeralDocScopeEnum.TENANT_PRIVATE_SCRATCH.value,
        }:
            return normalized
        return EphemeralDocScopeEnum.CONVERSATION_SCOPED.value

    @classmethod
    def resolve_ttl_seconds(cls, scope_type: str, ttl_seconds: int | None) -> int:
        default_ttl = _DEFAULT_TTL_SECONDS.get(
            scope_type,
            _DEFAULT_TTL_SECONDS[EphemeralDocScopeEnum.CONVERSATION_SCOPED.value],
        )
        if ttl_seconds is None:
            return default_ttl
        return max(60, min(int(ttl_seconds), _MAX_TTL_SECONDS))

    async def upsert_refs(
        self,
        *,
        conversation_id: int | None,
        agent_id: int | None,
        user_id: int | None,
        refs: list[dict[str, Any]],
    ) -> list[EphemeralDocument]:
        now = utc_now()
        stored: list[EphemeralDocument] = []
        for ref in refs:
            content = str(ref.get("content") or "").strip()
            if not content:
                continue
            scope_type = self.normalize_scope_type(ref.get("scope"))
            scope_key = self.build_scope_key(
                scope_type=scope_type,
                conversation_id=conversation_id,
                agent_id=agent_id,
                user_id=user_id,
            )
            title = (
                str(ref.get("title") or ref.get("source_ref") or "Ephemeral Document").strip()
                or "Ephemeral Document"
            )
            content_hash = _content_hash(content)
            ttl_seconds = self.resolve_ttl_seconds(
                scope_type,
                ref.get("ttl_seconds"),
            )
            expires_at = now + timedelta(seconds=ttl_seconds)
            existing = await self.repo.get_by_scope_hash(
                scope_type=scope_type,
                scope_key=scope_key,
                content_hash=content_hash,
            )
            if existing:
                existing.title = title
                existing.content_kind = str(ref.get("kind") or existing.content_kind or "text")
                existing.source_ref = str(ref.get("source_ref") or "") or None
                existing.status = EphemeralDocStatusEnum.ACTIVE.value
                existing.expires_at = expires_at
                existing.last_used_at = now
                existing.metadata_ = {
                    **(existing.metadata_ or {}),
                    "ttl_seconds": ttl_seconds,
                }
                await self.db.flush()
                stored.append(existing)
                continue

            doc = await self.create(
                {
                    "tenant_id": self.tenant_id,
                    "conversation_id": conversation_id,
                    "agent_id": agent_id,
                    "user_id": user_id,
                    "scope_type": scope_type,
                    "scope_key": scope_key,
                    "title": title,
                    "content_kind": str(ref.get("kind") or "text"),
                    "content": content,
                    "content_hash": content_hash,
                    "source_ref": str(ref.get("source_ref") or "") or None,
                    "status": EphemeralDocStatusEnum.ACTIVE.value,
                    "expires_at": expires_at,
                    "last_used_at": now,
                    "metadata_": {
                        "ttl_seconds": ttl_seconds,
                    },
                }
            )
            stored.append(doc)
        return stored

    async def list_runtime_documents(
        self,
        *,
        conversation_id: int | None,
        agent_id: int | None,
        user_id: int | None,
        limit: int = 50,
    ) -> list[EphemeralDocument]:
        scope_filters: list[tuple[str, str]] = []
        if conversation_id:
            scope_filters.append(
                (
                    EphemeralDocScopeEnum.CONVERSATION_SCOPED.value,
                    self.build_scope_key(
                        scope_type=EphemeralDocScopeEnum.CONVERSATION_SCOPED.value,
                        conversation_id=conversation_id,
                        agent_id=agent_id,
                        user_id=user_id,
                    ),
                )
            )
        if agent_id:
            scope_filters.append(
                (
                    EphemeralDocScopeEnum.AGENT_WORKSPACE_SCOPED.value,
                    self.build_scope_key(
                        scope_type=EphemeralDocScopeEnum.AGENT_WORKSPACE_SCOPED.value,
                        conversation_id=conversation_id,
                        agent_id=agent_id,
                        user_id=user_id,
                    ),
                )
            )
        if user_id:
            scope_filters.append(
                (
                    EphemeralDocScopeEnum.TENANT_PRIVATE_SCRATCH.value,
                    self.build_scope_key(
                        scope_type=EphemeralDocScopeEnum.TENANT_PRIVATE_SCRATCH.value,
                        conversation_id=conversation_id,
                        agent_id=agent_id,
                        user_id=user_id,
                    ),
                )
            )

        docs = await self.repo.list_active_for_scopes(
            scope_filters=scope_filters,
            now=utc_now(),
            limit=limit,
        )
        for doc in docs:
            doc.last_used_at = utc_now()
        if docs:
            await self.db.flush()
        return docs

    async def promote_to_knowledge_base(
        self,
        *,
        ephemeral_id: int,
        knowledge_base_id: int,
    ) -> KnowledgeDocument:
        ephemeral = await self.repo.get_by_id(ephemeral_id)
        if not ephemeral or ephemeral.is_deleted:
            raise NotFoundException(message="Ephemeral document not found")

        kb = await AdminKnowledgeBaseRepository(self.db).get_by_id(knowledge_base_id)
        if not kb or kb.is_deleted:
            raise NotFoundException(message="Knowledge base not found")

        if ephemeral.status == EphemeralDocStatusEnum.PROMOTED.value and ephemeral.promoted_document_id:
            existing = await self.db.get(KnowledgeDocument, ephemeral.promoted_document_id)
            if existing:
                return existing

        file_type = self._map_content_kind_to_document_type(ephemeral.content_kind)
        title = ephemeral.title or f"Ephemeral-{ephemeral.id}"
        document = KnowledgeDocument(
            tenant_id=getattr(kb, "tenant_id", None),
            knowledge_base_id=knowledge_base_id,
            attachment_id=None,
            file_name=title,
            file_type=file_type,
            file_size=len((ephemeral.content or "").encode("utf-8")),
            file_hash=ephemeral.content_hash,
            source_url=ephemeral.source_ref if ephemeral.content_kind == "url" else None,
            metadata_extra=ephemeral.content,
            status=DocumentStatusEnum.PENDING.value,
            error_message=None,
            error_stage=None,
            retry_count=0,
            chunk_count=0,
            token_count=0,
            char_count=0,
        )
        self.db.add(document)
        await self.db.flush()

        from app.ai.rag.processor import process_document

        process_document.delay(
            tenant_id=getattr(kb, "tenant_id", None),
            document_id=document.id,
        )

        ephemeral.status = EphemeralDocStatusEnum.PROMOTED.value
        ephemeral.promoted_knowledge_base_id = knowledge_base_id
        ephemeral.promoted_document_id = document.id
        ephemeral.updated_at = utc_now()
        await self.db.flush()
        return document

    @staticmethod
    def _map_content_kind_to_document_type(content_kind: str) -> str:
        if content_kind == "html":
            return DocumentTypeEnum.HTML.value
        if content_kind == "markdown":
            return DocumentTypeEnum.MD.value
        if content_kind == "csv":
            return DocumentTypeEnum.CSV.value
        if content_kind == "url":
            return DocumentTypeEnum.URL.value
        return DocumentTypeEnum.TXT.value


__all__ = ["EphemeralDocumentService"]
