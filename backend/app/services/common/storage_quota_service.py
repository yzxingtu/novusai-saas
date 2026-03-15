"""
存储配额服务 / Storage Quota Service

提供企业存储配额的统一计算逻辑，供平台端和企业端共用
Provides unified tenant storage quota calculation logic, shared by platform and tenant endpoints.
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tenant.attachment import Attachment
from app.models.tenant.tenant import Tenant


class StorageQuotaService:
    """
    存储配额服务 / Storage quota service.

    提供存储配额查询和检查的统一实现
    """

    def __init__(self, db: AsyncSession):
        """
        初始化服务 / Initialize service.

        Args:
            db: 异步数据库会话
        """
        self.db = db

    async def get_tenant_storage_stats(self, tenant_id: int) -> dict[str, Any]:
        """
        获取单个企业的存储统计信息 / Get tenant storage statistics.

        Args:
            tenant_id: 企业 ID

        Returns:
            存储统计信息
        """
        # 查询附件统计
        result = await self.db.execute(
            select(
                func.coalesce(func.sum(Attachment.size), 0).label("used_bytes"),
                func.count(Attachment.id).label("file_count"),
            ).where(
                Attachment.tenant_id == tenant_id,
                Attachment.is_deleted.is_(False),
            )
        )
        row = result.one()
        used_bytes = int(row.used_bytes)
        file_count = int(row.file_count)

        # 获取企业配额限制
        tenant = await self._get_tenant_with_plan(tenant_id)
        limit_gb = 0
        max_file_size_mb = 0
        if tenant:
            limit_gb = tenant.get_quota_value("storage_limit_gb", 0)
            max_file_size_mb = tenant.get_quota_value("max_file_size_mb", 0)

        return self._build_stats_response(
            used_bytes=used_bytes,
            file_count=file_count,
            limit_gb=limit_gb,
            max_file_size_mb=max_file_size_mb,
        )

    async def get_tenant_storage_stats_batch(
        self, tenant_ids: list[int]
    ) -> dict[int, dict[str, Any]]:
        """
        批量获取企业存储统计信息 / Batch get tenant storage statistics.

        Args:
            tenant_ids: 企业 ID 列表

        Returns:
            企业 ID 到存储统计的映射
        """
        if not tenant_ids:
            return {}

        # 批量查询附件统计
        result = await self.db.execute(
            select(
                Attachment.tenant_id,
                func.coalesce(func.sum(Attachment.size), 0).label("used_bytes"),
                func.count(Attachment.id).label("file_count"),
            ).where(
                Attachment.tenant_id.in_(tenant_ids),
                Attachment.is_deleted.is_(False),
            ).group_by(Attachment.tenant_id)
        )
        rows = result.all()

        # 构建统计映射
        stats_map: dict[int, dict[str, int]] = {}
        for row in rows:
            stats_map[row.tenant_id] = {
                "used_bytes": int(row.used_bytes),
                "file_count": int(row.file_count),
            }

        # 批量获取企业配额信息
        tenants = await self._get_tenants_with_plan(tenant_ids)

        result_map: dict[int, dict[str, Any]] = {}
        for tenant in tenants:
            stats = stats_map.get(tenant.id, {"used_bytes": 0, "file_count": 0})
            limit_gb = tenant.get_quota_value("storage_limit_gb", 0)
            max_file_size_mb = tenant.get_quota_value("max_file_size_mb", 0)

            result_map[tenant.id] = self._build_stats_response(
                used_bytes=stats["used_bytes"],
                file_count=stats["file_count"],
                limit_gb=limit_gb,
                max_file_size_mb=max_file_size_mb,
            )

        # 确保所有请求的企业都有统计数据（默认值）
        for tid in tenant_ids:
            if tid not in result_map:
                result_map[tid] = self._build_stats_response(
                    used_bytes=0,
                    file_count=0,
                    limit_gb=0,
                    max_file_size_mb=0,
                )

        return result_map

    async def get_used_bytes(self, tenant_id: int) -> int:
        """
        获取企业已使用的存储空间 / Get tenant used storage bytes.

        Args:
            tenant_id: 企业 ID

        Returns:
            已使用字节数
        """
        result = await self.db.execute(
            select(func.coalesce(func.sum(Attachment.size), 0)).where(
                Attachment.tenant_id == tenant_id,
                Attachment.is_deleted.is_(False),
            )
        )
        return int(result.scalar() or 0)

    async def get_file_count(self, tenant_id: int) -> int:
        """
        获取企业附件总数 / Get tenant attachment count.

        Args:
            tenant_id: 企业 ID

        Returns:
            附件数量
        """
        result = await self.db.execute(
            select(func.count(Attachment.id)).where(
                Attachment.tenant_id == tenant_id,
                Attachment.is_deleted.is_(False),
            )
        )
        return int(result.scalar() or 0)

    async def _get_tenant_with_plan(self, tenant_id: int) -> Tenant | None:
        """
        获取企业信息（含套餐关联）/ Get tenant with plan.

        Args:
            tenant_id: 企业 ID

        Returns:
            企业实例或 None
        """
        result = await self.db.execute(
            select(Tenant)
            .options(selectinload(Tenant.tenant_plan))
            .where(
                Tenant.id == tenant_id,
                Tenant.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def _get_tenants_with_plan(self, tenant_ids: list[int]) -> list[Tenant]:
        """
        批量获取企业信息（含套餐关联）/ Batch get tenants with plan.

        Args:
            tenant_ids: 企业 ID 列表

        Returns:
            企业列表
        """
        result = await self.db.execute(
            select(Tenant)
            .options(selectinload(Tenant.tenant_plan))
            .where(
                Tenant.id.in_(tenant_ids),
                Tenant.is_deleted.is_(False),
            )
        )
        return list(result.scalars().all())

    def _build_stats_response(
        self,
        used_bytes: int,
        file_count: int,
        limit_gb: int,
        max_file_size_mb: int = 0,
    ) -> dict[str, Any]:
        """
        构建统计响应数据 / Build stats response.

        Args:
            used_bytes: 已使用字节数
            file_count: 文件数量
            limit_gb: 限制（GB）
            max_file_size_mb: 单文件大小限制（MB）

        Returns:
            统计响应字典
        """
        limit_bytes = limit_gb * 1024 * 1024 * 1024 if limit_gb > 0 else 0
        unlimited = limit_gb == 0
        usage_percent = round(used_bytes / limit_bytes * 100, 2) if limit_bytes > 0 else 0.0
        remaining_bytes = max(0, limit_bytes - used_bytes) if limit_bytes > 0 else 0

        return {
            "used_bytes": used_bytes,
            "limit_bytes": limit_bytes,
            "limit_gb": limit_gb,
            "remaining_bytes": remaining_bytes,
            "usage_percent": usage_percent,
            "file_count": file_count,
            "max_file_size_mb": max_file_size_mb,
            "unlimited": unlimited,
        }


__all__ = ["StorageQuotaService"]
