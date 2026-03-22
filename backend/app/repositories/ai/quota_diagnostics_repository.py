"""
AI 配额诊断 Repository / AI quota diagnostics repository
"""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.query_parser import QuerySpec
from app.models.ai import TenantModelRateLimit, TenantQuota
from app.models.tenant import Tenant


class AIQuotaDiagnosticsRepository:
    """
    AI 配额诊断数据访问层 / AI quota diagnostics data-access layer.

    Provides read-side queries for admin diagnostics dashboards.
    提供管理端诊断页所需的只读聚合查询。
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_quota_rules(
        self,
        spec: QuerySpec,
    ) -> tuple[list[TenantQuota], int]:
        stmt = select(TenantQuota).where(TenantQuota.is_deleted.is_(False)).options(
            selectinload(TenantQuota.model),
            selectinload(TenantQuota.tenant),
        )
        count_stmt = select(func.count(TenantQuota.id)).where(
            TenantQuota.is_deleted.is_(False)
        )

        stmt = self._apply_quota_filters(stmt, spec)
        count_stmt = self._apply_quota_filters(count_stmt, spec)
        stmt = self._apply_quota_sort(stmt, spec)
        stmt = stmt.offset((spec.page - 1) * spec.size).limit(spec.size)

        items_result = await self.db.execute(stmt)
        total_result = await self.db.execute(count_stmt)
        return list(items_result.scalars().all()), int(total_result.scalar() or 0)

    async def list_rate_limit_rules(
        self,
        spec: QuerySpec,
    ) -> tuple[list[TenantModelRateLimit], int]:
        stmt = select(TenantModelRateLimit).where(
            TenantModelRateLimit.is_deleted.is_(False)
        ).options(
            selectinload(TenantModelRateLimit.model),
        )
        count_stmt = select(func.count(TenantModelRateLimit.id)).where(
            TenantModelRateLimit.is_deleted.is_(False)
        )

        stmt = self._apply_rate_limit_filters(stmt, spec)
        count_stmt = self._apply_rate_limit_filters(count_stmt, spec)
        stmt = self._apply_rate_limit_sort(stmt, spec)
        stmt = stmt.offset((spec.page - 1) * spec.size).limit(spec.size)

        items_result = await self.db.execute(stmt)
        total_result = await self.db.execute(count_stmt)
        return list(items_result.scalars().all()), int(total_result.scalar() or 0)

    async def list_all_quota_rules(self) -> list[TenantQuota]:
        stmt = select(TenantQuota).where(TenantQuota.is_deleted.is_(False)).options(
            selectinload(TenantQuota.model),
            selectinload(TenantQuota.tenant),
        ).order_by(TenantQuota.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_all_rate_limit_rules(self) -> list[TenantModelRateLimit]:
        stmt = select(TenantModelRateLimit).where(
            TenantModelRateLimit.is_deleted.is_(False)
        ).options(
            selectinload(TenantModelRateLimit.model),
        ).order_by(TenantModelRateLimit.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_tenant_name_map(
        self,
        tenant_ids: set[int],
    ) -> dict[int, str]:
        if not tenant_ids:
            return {}

        stmt = select(Tenant.id, Tenant.name).where(Tenant.id.in_(tenant_ids))
        result = await self.db.execute(stmt)
        return {tenant_id: name for tenant_id, name in result.all()}

    def _apply_quota_filters(
        self,
        stmt: Select,
        spec: QuerySpec,
    ) -> Select:
        for rule in spec.filters:
            value = self._coerce_value(rule.value)
            if rule.field == "tenant_id":
                stmt = stmt.where(TenantQuota.tenant_id == value)
            elif rule.field == "model_id":
                if value in ("global", "null", None):
                    stmt = stmt.where(TenantQuota.model_id.is_(None))
                else:
                    stmt = stmt.where(TenantQuota.model_id == value)
            elif rule.field == "period":
                stmt = stmt.where(TenantQuota.period == str(value))
            elif rule.field == "quota_type":
                stmt = stmt.where(TenantQuota.quota_type == str(value))
            elif rule.field == "is_active":
                stmt = stmt.where(TenantQuota.is_active.is_(bool(value)))
        return stmt

    def _apply_rate_limit_filters(
        self,
        stmt: Select,
        spec: QuerySpec,
    ) -> Select:
        for rule in spec.filters:
            value = self._coerce_value(rule.value)
            if rule.field == "tenant_id":
                stmt = stmt.where(TenantModelRateLimit.tenant_id == value)
            elif rule.field == "model_id":
                stmt = stmt.where(TenantModelRateLimit.model_id == value)
            elif rule.field == "is_active":
                stmt = stmt.where(TenantModelRateLimit.is_active.is_(bool(value)))
        return stmt

    def _apply_quota_sort(self, stmt: Select, spec: QuerySpec) -> Select:
        sort_fields = spec.sort or ["-created_at"]
        for sort_field in sort_fields:
            is_desc = sort_field.startswith("-")
            field_name = sort_field[1:] if is_desc else sort_field
            column = {
                "created_at": TenantQuota.created_at,
                "updated_at": TenantQuota.updated_at,
                "limit": TenantQuota.limit,
                "tenant_id": TenantQuota.tenant_id,
                "model_id": TenantQuota.model_id,
            }.get(field_name, TenantQuota.created_at)
            stmt = stmt.order_by(column.desc() if is_desc else column.asc())
        return stmt

    def _apply_rate_limit_sort(self, stmt: Select, spec: QuerySpec) -> Select:
        sort_fields = spec.sort or ["-created_at"]
        for sort_field in sort_fields:
            is_desc = sort_field.startswith("-")
            field_name = sort_field[1:] if is_desc else sort_field
            column = {
                "created_at": TenantModelRateLimit.created_at,
                "updated_at": TenantModelRateLimit.updated_at,
                "tenant_id": TenantModelRateLimit.tenant_id,
                "model_id": TenantModelRateLimit.model_id,
            }.get(field_name, TenantModelRateLimit.created_at)
            stmt = stmt.order_by(column.desc() if is_desc else column.asc())
        return stmt

    @staticmethod
    def _coerce_value(value):
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered == "true":
                return True
            if lowered == "false":
                return False
            if lowered.isdigit():
                return int(lowered)
            return value.strip()
        return value


__all__ = ["AIQuotaDiagnosticsRepository"]
