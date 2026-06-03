"""
Profile snapshot repository / 画像快照仓储
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.base_repository import TenantRepository
from app.models.ai.profile_snapshot import ProfileSnapshot


class ProfileSnapshotRepository(TenantRepository[ProfileSnapshot]):
    model = ProfileSnapshot

    async def get_by_scope(
        self,
        *,
        scope_type: str,
        scope_key: str,
    ) -> ProfileSnapshot | None:
        result = await self.db.execute(
            select(self.model).where(
                self.model.tenant_id == self.tenant_id,
                self.model.scope_type == scope_type,
                self.model.scope_key == scope_key,
                self.model.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()


__all__ = ["ProfileSnapshotRepository"]
