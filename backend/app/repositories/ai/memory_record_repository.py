"""
Long-term memory repository / 长期记忆仓储
"""

from __future__ import annotations

from sqlalchemy import and_, case, func, or_, select, update

from app.core.base_model import utc_now
from app.core.base_repository import TenantRepository
from app.enums.memory import MemoryStatusEnum
from app.models.ai.memory_record import MemoryRecord


class MemoryRecordRepository(TenantRepository[MemoryRecord]):
    model = MemoryRecord

    async def get_by_scope_type_hash(
        self,
        *,
        scope_type: str,
        scope_key: str,
        memory_type: str,
        content_hash: str,
    ) -> MemoryRecord | None:
        result = await self.db.execute(
            select(self.model).where(
                and_(
                    self.model.tenant_id == self.tenant_id,
                    self.model.scope_type == scope_type,
                    self.model.scope_key == scope_key,
                    self.model.memory_type == memory_type,
                    self.model.content_hash == content_hash,
                    self.model.is_deleted.is_(False),
                )
            )
        )
        return result.scalar_one_or_none()

    async def search_for_recall(
        self,
        *,
        scope_type: str,
        scope_key: str,
        query_text: str,
        limit: int = 5,
        query_embedding: list[float] | None = None,
        embedding_model_id: int | None = None,
    ) -> list[MemoryRecord]:
        normalized = (query_text or "").strip()
        stmt = select(self.model).where(
            self.model.tenant_id == self.tenant_id,
            self.model.scope_type == scope_type,
            self.model.scope_key == scope_key,
            self.model.is_deleted.is_(False),
            self.model.status.in_(
                [
                    MemoryStatusEnum.CANDIDATE.value,
                    MemoryStatusEnum.VERIFIED.value,
                ]
            ),
        )

        if normalized:
            escaped = normalized.replace("%", "\\%").replace("_", "\\_")
            fuzzy = f"%{escaped}%"
            text_match = or_(
                self.model.content.ilike(fuzzy),
                self.model.summary.ilike(fuzzy),
            )
            exact_boost = case(
                (self.model.content.ilike(fuzzy), 4),
                (self.model.summary.ilike(fuzzy), 2),
                else_=0,
            )
            if query_embedding is not None and embedding_model_id is not None:
                distance_expr = self.model.embedding.cosine_distance(query_embedding)
                semantic_match = and_(
                    self.model.embedding.isnot(None),
                    self.model.embedding_model_id == embedding_model_id,
                    distance_expr <= 0.45,
                )
                stmt = stmt.where(or_(text_match, semantic_match))
            else:
                distance_expr = None
                stmt = stmt.where(text_match)
        else:
            distance_expr = None
            exact_boost = case((self.model.id.is_not(None), 0), else_=0)

        order_by = [
            exact_boost.desc(),
            self.model.importance.desc(),
            self.model.updated_at.desc(),
        ]
        if distance_expr is not None:
            order_by = [
                exact_boost.desc(),
                distance_expr.asc(),
                self.model.importance.desc(),
                self.model.updated_at.desc(),
            ]

        stmt = stmt.order_by(*order_by).limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_for_scope(
        self,
        *,
        scope_type: str,
        scope_key: str,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        result = await self.db.execute(
            select(self.model)
            .where(
                self.model.tenant_id == self.tenant_id,
                self.model.scope_type == scope_type,
                self.model.scope_key == scope_key,
                self.model.is_deleted.is_(False),
                self.model.status.in_(
                    [
                        MemoryStatusEnum.CANDIDATE.value,
                        MemoryStatusEnum.VERIFIED.value,
                    ]
                ),
            )
            .order_by(
                self.model.importance.desc(),
                self.model.updated_at.desc(),
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_for_scope(
        self,
        *,
        scope_type: str,
        scope_key: str,
    ) -> int:
        result = await self.db.execute(
            select(func.count(self.model.id)).where(
                self.model.tenant_id == self.tenant_id,
                self.model.scope_type == scope_type,
                self.model.scope_key == scope_key,
                self.model.is_deleted.is_(False),
            )
        )
        return int(result.scalar() or 0)

    async def delete_for_scope(
        self,
        *,
        scope_type: str,
        scope_key: str,
    ) -> int:
        now = utc_now()
        result = await self.db.execute(
            update(self.model)
            .where(
                self.model.tenant_id == self.tenant_id,
                self.model.scope_type == scope_type,
                self.model.scope_key == scope_key,
                self.model.is_deleted.is_(False),
            )
            .values(
                is_deleted=True,
                deleted_at=now,
                updated_at=now,
            )
        )
        return int(result.rowcount or 0)


__all__ = ["MemoryRecordRepository"]
