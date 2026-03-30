"""
Ephemeral document repository / 临时资料文档仓储
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, or_, select

from app.core.base_repository import TenantRepository
from app.enums.knowledge_base import EphemeralDocStatusEnum
from app.models.ai.ephemeral_document import EphemeralDocument


class EphemeralDocumentRepository(TenantRepository[EphemeralDocument]):
    model = EphemeralDocument

    async def get_by_scope_hash(
        self,
        *,
        scope_type: str,
        scope_key: str,
        content_hash: str,
    ) -> EphemeralDocument | None:
        result = await self.db.execute(
            select(self.model).where(
                self.model.tenant_id == self.tenant_id,
                self.model.scope_type == scope_type,
                self.model.scope_key == scope_key,
                self.model.content_hash == content_hash,
                self.model.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def list_active_for_scopes(
        self,
        *,
        scope_filters: list[tuple[str, str]],
        now: datetime,
        limit: int = 50,
    ) -> list[EphemeralDocument]:
        if not scope_filters:
            return []

        conditions = [
            and_(
                self.model.scope_type == scope_type,
                self.model.scope_key == scope_key,
            )
            for scope_type, scope_key in scope_filters
        ]
        result = await self.db.execute(
            select(self.model).where(
                self.model.tenant_id == self.tenant_id,
                self.model.is_deleted.is_(False),
                self.model.status == EphemeralDocStatusEnum.ACTIVE.value,
                or_(self.model.expires_at.is_(None), self.model.expires_at > now),
                or_(*conditions),
            ).order_by(
                self.model.last_used_at.desc().nullslast(),
                self.model.updated_at.desc(),
                self.model.id.desc(),
            ).limit(limit)
        )
        return list(result.scalars().all())


__all__ = ["EphemeralDocumentRepository"]
