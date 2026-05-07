"""
Long-term memory service / 长期记忆服务
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from app.ai.internal_ai_service import InternalAIService
from app.ai.rag.text_cleaner import clean_for_embedding
from app.ai.text_semantics import extract_memory_keywords
from app.core.base_model import utc_now
from app.core.base_service import TenantService
from app.enums.ai import CallTypeEnum
from app.enums.memory import (
    MemoryScopeTypeEnum,
    MemoryStatusEnum,
    MemoryTypeEnum,
)
from app.models.ai.memory_record import MemoryRecord
from app.models.ai.profile_snapshot import ProfileSnapshot
from app.repositories.ai.memory_record_repository import MemoryRecordRepository
from app.repositories.ai.model_repository import AIModelRepository
from app.repositories.ai.profile_snapshot_repository import ProfileSnapshotRepository


def _memory_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest()


def _extract_keywords(text: str, *, limit: int = 12) -> list[str]:
    return extract_memory_keywords(text, limit=limit)


@dataclass
class EmbeddingTarget:
    model_id: int
    model_code: str
    provider_code: str


class LongTermMemoryService(TenantService[MemoryRecord, MemoryRecordRepository]):
    model = MemoryRecord
    repository_class = MemoryRecordRepository

    def __init__(self, db, tenant_id: int):
        super().__init__(db, tenant_id)
        self.profile_repo = ProfileSnapshotRepository(db, tenant_id)

    @staticmethod
    def build_scope_key(
        scope_type: str,
        *,
        agent_id: int | None = None,
        user_id: int | None = None,
    ) -> str:
        if scope_type == MemoryScopeTypeEnum.USER_AGENT.value:
            return f"user:{user_id or 0}:agent:{agent_id or 0}"
        if scope_type == MemoryScopeTypeEnum.TENANT_AGENT.value:
            return f"tenant_agent:{agent_id or 0}"
        if scope_type == MemoryScopeTypeEnum.TENANT_SHARED.value:
            return "tenant_shared"
        return f"conversation:{user_id or 0}:agent:{agent_id or 0}"

    async def capture_records(
        self,
        *,
        agent_id: int,
        user_id: int,
        source_kind: str,
        source_ref: str | None,
        items_by_type: dict[str, list[str]],
        scope_type: str = MemoryScopeTypeEnum.USER_AGENT.value,
        status: str = MemoryStatusEnum.CANDIDATE.value,
        expires_at: datetime | None = None,
    ) -> list[MemoryRecord]:
        scope_key = self.build_scope_key(
            scope_type,
            agent_id=agent_id,
            user_id=user_id,
        )
        captured: list[MemoryRecord] = []
        embedding_target = await self._resolve_embedding_target()

        texts_to_embed: list[str] = []
        ordered_items: list[tuple[str, str]] = []
        for memory_type, items in items_by_type.items():
            for raw_text in items:
                text = (raw_text or "").strip()
                if not text:
                    continue
                ordered_items.append((memory_type, text))
                texts_to_embed.append(text)

        embeddings_by_key: dict[tuple[str, str], list[float]] = {}
        if embedding_target and texts_to_embed:
            embeddings = await self._generate_embeddings(
                texts_to_embed, embedding_target
            )
            for item, embedding in zip(ordered_items, embeddings, strict=False):
                if embedding:
                    embeddings_by_key[item] = embedding

        for memory_type, text in ordered_items:
            content_hash = _memory_hash(text)
            existing = await self.repo.get_by_scope_type_hash(
                scope_type=scope_type,
                scope_key=scope_key,
                memory_type=memory_type,
                content_hash=content_hash,
            )
            keywords = _extract_keywords(text)
            embedding = embeddings_by_key.get((memory_type, text))

            if existing:
                existing.summary = text[:300]
                existing.importance = max(
                    int(getattr(existing, "importance", 50) or 50), 60
                )
                existing.source_kind = source_kind
                existing.source_ref = source_ref
                existing.status = status
                existing.expires_at = expires_at
                existing.keywords = keywords
                if embedding is not None and embedding_target:
                    existing.embedding = embedding
                    existing.embedding_model_id = embedding_target.model_id
                    existing.embedding_dimensions = len(embedding)
                existing.updated_at = utc_now()
                await self.db.flush()
                captured.append(existing)
                continue

            record = await self.create(
                {
                    "tenant_id": self.tenant_id,
                    "agent_id": agent_id,
                    "user_id": user_id,
                    "scope_type": scope_type,
                    "scope_key": scope_key,
                    "memory_type": memory_type,
                    "content": text,
                    "summary": text[:300],
                    "keywords": keywords,
                    "content_hash": content_hash,
                    "embedding_model_id": embedding_target.model_id
                    if embedding_target and embedding is not None
                    else None,
                    "embedding_dimensions": len(embedding)
                    if embedding is not None
                    else None,
                    "embedding": embedding,
                    "confidence": 70,
                    "importance": 60,
                    "source_kind": source_kind,
                    "source_ref": source_ref,
                    "status": status,
                    "expires_at": expires_at,
                    "metadata_": {},
                }
            )
            captured.append(record)

        if captured:
            await self.refresh_profile_snapshot(
                agent_id=agent_id,
                user_id=user_id,
                scope_type=scope_type,
            )

        return captured

    async def recall(
        self,
        *,
        agent_id: int,
        user_id: int,
        query_text: str,
        limit: int = 5,
        scope_type: str = MemoryScopeTypeEnum.USER_AGENT.value,
    ) -> list[MemoryRecord]:
        scope_key = self.build_scope_key(
            scope_type,
            agent_id=agent_id,
            user_id=user_id,
        )
        query_embedding: list[float] | None = None
        embedding_target = await self._resolve_embedding_target()
        if embedding_target and (query_text or "").strip():
            embeddings = await self._generate_embeddings([query_text], embedding_target)
            query_embedding = embeddings[0] if embeddings else None

        records = await self.repo.search_for_recall(
            scope_type=scope_type,
            scope_key=scope_key,
            query_text=query_text,
            limit=limit,
            query_embedding=query_embedding,
            embedding_model_id=embedding_target.model_id
            if query_embedding and embedding_target
            else None,
        )
        now = utc_now()
        for record in records:
            record.last_recalled_at = now
        if records:
            await self.db.flush()
        return records

    async def profile(
        self,
        *,
        agent_id: int,
        user_id: int,
        limit: int = 10,
        scope_type: str = MemoryScopeTypeEnum.USER_AGENT.value,
    ) -> dict | None:
        _ = limit
        scope_key = self.build_scope_key(
            scope_type,
            agent_id=agent_id,
            user_id=user_id,
        )
        snapshot = await self.profile_repo.get_by_scope(
            scope_type=scope_type,
            scope_key=scope_key,
        )
        if snapshot is None:
            snapshot = await self.refresh_profile_snapshot(
                agent_id=agent_id,
                user_id=user_id,
                scope_type=scope_type,
            )
        if snapshot is None:
            return None
        return {
            "scope_type": snapshot.scope_type,
            "scope_key": snapshot.scope_key,
            "summary": snapshot.summary,
            "profile": snapshot.profile_json or {},
            "record_count": snapshot.record_count,
        }

    async def search(
        self,
        *,
        agent_id: int,
        user_id: int,
        query_text: str,
        limit: int = 10,
        scope_type: str = MemoryScopeTypeEnum.USER_AGENT.value,
    ) -> list[MemoryRecord]:
        scope_key = self.build_scope_key(
            scope_type,
            agent_id=agent_id,
            user_id=user_id,
        )
        query_embedding: list[float] | None = None
        embedding_target = await self._resolve_embedding_target()
        if embedding_target and (query_text or "").strip():
            embeddings = await self._generate_embeddings([query_text], embedding_target)
            query_embedding = embeddings[0] if embeddings else None

        return await self.repo.search_for_recall(
            scope_type=scope_type,
            scope_key=scope_key,
            query_text=query_text,
            limit=limit,
            query_embedding=query_embedding,
            embedding_model_id=embedding_target.model_id
            if query_embedding and embedding_target
            else None,
        )

    async def refresh_profile_snapshot(
        self,
        *,
        agent_id: int,
        user_id: int,
        scope_type: str = MemoryScopeTypeEnum.USER_AGENT.value,
    ) -> ProfileSnapshot | None:
        scope_key = self.build_scope_key(
            scope_type,
            agent_id=agent_id,
            user_id=user_id,
        )
        records = await self.repo.list_for_scope(
            scope_type=scope_type,
            scope_key=scope_key,
            limit=50,
        )
        snapshot = await self.profile_repo.get_by_scope(
            scope_type=scope_type,
            scope_key=scope_key,
        )

        if not records:
            if snapshot is None:
                return None
            snapshot.summary = None
            snapshot.profile_json = {}
            snapshot.record_count = 0
            snapshot.source_updated_at = None
            snapshot.updated_at = utc_now()
            await self.db.flush()
            return snapshot

        profile_json, summary = self._build_profile_payload(records)
        latest_source_updated_at = max(
            (
                getattr(record, "updated_at", None)
                or getattr(record, "created_at", None)
                for record in records
            ),
            default=None,
        )

        if snapshot is None:
            snapshot = await self.profile_repo.create(
                {
                    "tenant_id": self.tenant_id,
                    "agent_id": agent_id,
                    "user_id": user_id,
                    "scope_type": scope_type,
                    "scope_key": scope_key,
                    "summary": summary,
                    "profile_json": profile_json,
                    "record_count": len(records),
                    "source_updated_at": latest_source_updated_at,
                    "metadata_": {},
                }
            )
        else:
            snapshot.summary = summary
            snapshot.profile_json = profile_json
            snapshot.record_count = len(records)
            snapshot.source_updated_at = latest_source_updated_at
            snapshot.updated_at = utc_now()
            await self.db.flush()
        return snapshot

    async def _resolve_embedding_target(self) -> EmbeddingTarget | None:
        model = await AIModelRepository(
            self.db
        ).get_first_active_embedding_with_provider()
        provider = getattr(model, "provider", None) if model else None
        if not model or not provider:
            return None
        return EmbeddingTarget(
            model_id=int(model.id),
            model_code=str(model.code),
            provider_code=str(provider.code),
        )

    async def _generate_embeddings(
        self,
        texts: list[str],
        target: EmbeddingTarget,
    ) -> list[list[float]]:
        cleaned = [clean_for_embedding(text) for text in texts if (text or "").strip()]
        if not cleaned:
            return []
        try:
            response = await InternalAIService(self.db).embedding(
                provider_code=target.provider_code,
                texts=cleaned,
                model=target.model_code,
                tenant_id=self.tenant_id,
                call_type=CallTypeEnum.INTERNAL_MEMORY.value,
            )
        except Exception:
            return []
        return list(response.embeddings or [])

    @staticmethod
    def _build_profile_payload(records: list[MemoryRecord]) -> tuple[dict, str | None]:
        buckets: dict[str, list[str]] = {
            "preferences": [],
            "constraints": [],
            "facts": [],
            "decisions": [],
            "patterns": [],
            "task_summaries": [],
            "corrections": [],
            "relationships": [],
        }
        mapping = {
            MemoryTypeEnum.PREFERENCE.value: "preferences",
            MemoryTypeEnum.CONSTRAINT.value: "constraints",
            MemoryTypeEnum.FACT.value: "facts",
            MemoryTypeEnum.DECISION.value: "decisions",
            MemoryTypeEnum.PATTERN.value: "patterns",
            MemoryTypeEnum.TASK_SUMMARY.value: "task_summaries",
            MemoryTypeEnum.CORRECTION.value: "corrections",
            MemoryTypeEnum.RELATIONSHIP.value: "relationships",
        }
        for record in records:
            bucket_key = mapping.get(str(record.memory_type))
            if not bucket_key:
                continue
            value = (record.summary or record.content or "").strip()
            if not value or value in buckets[bucket_key]:
                continue
            if len(buckets[bucket_key]) >= 6:
                continue
            buckets[bucket_key].append(value)

        profile_json = {key: value for key, value in buckets.items() if value}
        if not profile_json:
            return {}, None

        summary_parts: list[str] = []
        labels = [
            ("preferences", "Preferences"),
            ("constraints", "Constraints"),
            ("facts", "Facts"),
            ("decisions", "Decisions"),
            ("patterns", "Patterns"),
            ("corrections", "Corrections"),
        ]
        for key, label in labels:
            values = profile_json.get(key) or []
            if not values:
                continue
            summary_parts.append(f"{label}: {'; '.join(values[:2])}")
            if len(summary_parts) >= 4:
                break

        return profile_json, "\n".join(summary_parts) or None


def build_memory_capture_payload_from_session_delta(
    delta: dict[str, list[str]],
) -> dict[str, list[str]]:
    return {
        MemoryTypeEnum.PREFERENCE.value: list(delta.get("preferences") or []),
        MemoryTypeEnum.CONSTRAINT.value: list(delta.get("constraints") or []),
        MemoryTypeEnum.FACT.value: list(delta.get("verified_facts") or []),
        MemoryTypeEnum.TASK_SUMMARY.value: list(delta.get("task_states") or []),
    }


__all__ = [
    "LongTermMemoryService",
    "build_memory_capture_payload_from_session_delta",
]
