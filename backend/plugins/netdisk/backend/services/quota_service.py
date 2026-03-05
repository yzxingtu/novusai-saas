"""
配额管理 Service — 统计查询必须在此层，Controller 不直接查 DB
"""

from __future__ import annotations

from app.core.base_service import TenantService
from app.core.i18n import _
from app.exceptions import BusinessException


class QuotaService(TenantService):
    def __init__(self, db, tenant_id: int | None):
        # This service orchestrates multiple repositories and does not rely on BaseService.repo.
        self.db = db
        self.tenant_id = tenant_id

    async def get_quota(self) -> dict:
        """获取当前租户配额信息（Controller 通过此方法，不直接查 DB）"""
        from ..repositories.quota_repository import QuotaRepository
        repo = QuotaRepository(self.db, self.tenant_id)
        quota = await repo.get_or_create()
        return {
            "quota_bytes": quota.quota_bytes,
            "used_bytes": quota.used_bytes,
            "free_bytes": quota.free_bytes,
            "used_percent": quota.used_percent,
        }

    async def check_quota(self, upload_size: int) -> None:
        """上传前检查配额，不足时抛 BusinessException"""
        from ..repositories.quota_repository import QuotaRepository
        repo = QuotaRepository(self.db, self.tenant_id)
        quota = await repo.get_or_create()
        if not quota.check_capacity(upload_size):
            free_gb = quota.free_bytes / 1024 ** 3
            raise BusinessException(
                message=_("plugin.netdisk.error.quota_exceeded").format(free=f"{free_gb:.2f}"),
                status_code=429,
            )

    async def add_used(self, delta: int) -> None:
        """更新已用配额（上传/删除后调用）"""
        from ..repositories.quota_repository import QuotaRepository
        repo = QuotaRepository(self.db, self.tenant_id)
        await repo.add_used(delta)
        await self.db.commit()

    async def recalculate(self) -> int:
        """重算并更新 used_bytes，返回实际用量"""
        from ..repositories.node_repository import NodeRepository
        from ..repositories.quota_repository import QuotaRepository

        node_repo = NodeRepository(self.db, self.tenant_id)
        actual = await node_repo.sum_folder_size()

        quota_repo = QuotaRepository(self.db, self.tenant_id)
        await quota_repo.recalculate(actual)
        await self.db.commit()
        return actual

    # ── 管理端：统计所有租户配额（在 Service 层查询，Controller 不查 DB）

    async def admin_list_quotas(self, page: int = 1, size: int = 20) -> dict:
        """管理端：分页列出所有租户配额"""
        from sqlalchemy import func, select

        from ..models.quota import Quota

        total_result = await self.db.execute(select(func.count(Quota.id)))
        total = total_result.scalar_one() or 0

        result = await self.db.execute(
            select(Quota)
            .order_by(Quota.used_bytes.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        items = result.scalars().all()
        return {"items": items, "total": total}

    async def admin_update_quota(self, tenant_id: int, quota_bytes: int) -> None:
        """管理端：修改指定租户配额"""
        from sqlalchemy import update

        from app.core.base_model import utc_now
        from ..models.quota import Quota

        await self.db.execute(
            update(Quota)
            .where(Quota.tenant_id == tenant_id)
            .values(quota_bytes=quota_bytes, updated_at=utc_now())
        )
        await self.db.commit()

    async def admin_stats(self) -> dict:
        """管理端 Dashboard 统计数据（在 Service 层计算）"""
        from sqlalchemy import func, select

        from ..models.node import FileNode, NodeTypeEnum
        from ..models.quota import Quota
        from ..models.share import Share

        total_quota = await self.db.execute(select(func.sum(Quota.quota_bytes)))
        total_used  = await self.db.execute(select(func.sum(Quota.used_bytes)))
        total_files = await self.db.execute(
            select(func.count(FileNode.id))
            .where(FileNode.is_deleted.is_(False), FileNode.node_type == NodeTypeEnum.FILE.value)
        )
        total_shares = await self.db.execute(
            select(func.count(Share.id)).where(Share.is_active.is_(True))
        )

        return {
            "total_quota_bytes": total_quota.scalar_one() or 0,
            "total_used_bytes":  total_used.scalar_one() or 0,
            "total_files":       total_files.scalar_one() or 0,
            "total_shares":      total_shares.scalar_one() or 0,
        }
