"""存储配额 Repository / Storage quota repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.base_repository import TenantRepository

if TYPE_CHECKING:
    from ..models.quota import Quota


class QuotaRepository(TenantRepository["Quota"]):

    async def get_or_create(self, default_bytes: int = 10 * 1024 ** 3) -> Quota:
        """获取当前企业配额，不存在则创建默认记录（幂等） / Get tenant quota, create default if missing (idempotent)."""
        from app.core.base_model import utc_now
        from ..models.quota import Quota

        result = await self.db.execute(
            select(Quota).where(Quota.tenant_id == self.tenant_id)
        )
        quota = result.scalar_one_or_none()
        if quota is None:
            quota = Quota(
                tenant_id=self.tenant_id,
                quota_bytes=default_bytes,
                used_bytes=0,
                updated_at=utc_now(),
            )
            self.db.add(quota)
            await self.db.flush()
        return quota

    async def add_used(self, delta: int) -> None:
        """增加已用量（delta 可为负数表示释放） / Add used bytes (delta can be negative to release)."""
        from sqlalchemy import update

        from ..models.quota import Quota

        quota = await self.get_or_create()
        new_used = max(0, quota.used_bytes + delta)
        await self.db.execute(
            update(Quota)
            .where(Quota.tenant_id == self.tenant_id)
            .values(used_bytes=new_used)
        )

    async def recalculate(self, actual_bytes: int) -> None:
        """重算配额 used_bytes（定时任务或手动触发） / Recompute used_bytes (cron or manual)."""
        from sqlalchemy import update

        from app.core.base_model import utc_now
        from ..models.quota import Quota

        await self.db.execute(
            update(Quota)
            .where(Quota.tenant_id == self.tenant_id)
            .values(used_bytes=actual_bytes, updated_at=utc_now())
        )
