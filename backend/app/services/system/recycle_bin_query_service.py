"""Recycle-bin read helpers shared by registry utilities."""

from __future__ import annotations

from sqlalchemy import select

from app.enums.recycle import RecycleStageEnum
from app.models.tenant.tenant import Tenant


class RecycleBinQueryService:
    """Read-side helpers for recycle-bin registry utilities."""

    def __init__(self, db):
        self._db = db

    async def get_tenant_name_map(self, tenant_ids: list[int]) -> dict[int, str]:
        if not tenant_ids:
            return {}

        rows = await self._db.execute(
            select(Tenant.id, Tenant.name).where(Tenant.id.in_(tenant_ids))
        )
        return {row[0]: row[1] for row in rows.all()}

    async def list_global_deleted_ids(
        self,
        *,
        model_cls,
        delete_scope: int | None,
        tenant_field: str | None,
        tenant_id: int | None,
    ) -> list[int]:
        stmt = select(model_cls.id).where(
            model_cls.is_deleted.is_(True),
            model_cls.recycle_stage == RecycleStageEnum.GLOBAL.value,
        )

        if delete_scope is not None:
            stmt = stmt.where(model_cls.delete_level == delete_scope)

        if tenant_id is not None and tenant_field:
            stmt = stmt.where(getattr(model_cls, tenant_field) == tenant_id)

        result = await self._db.execute(stmt.order_by(model_cls.id))
        return list(result.scalars().all())


__all__ = ["RecycleBinQueryService"]
