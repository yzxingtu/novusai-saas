"""AI provider health read models / AI 供应商健康读模型。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.failover import FailoverService
from app.models.ai.provider import AIProvider


class AIHealthReadModelService:
    """Build admin AI health monitoring read models / 构建管理员 AI 健康监控读模型。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_provider_health_statuses(self) -> list[dict[str, Any]]:
        statuses = await FailoverService.get_all_provider_health()
        provider_ids = {
            int(status.get("provider_id") or 0)
            for status in statuses
            if int(status.get("provider_id") or 0) > 0
        }
        icon_map = await self._get_provider_icon_map(provider_ids)
        for status in statuses:
            status["provider_icon"] = icon_map.get(status.get("provider_id"))
        return statuses

    async def _get_provider_icon_map(
        self,
        provider_ids: set[int],
    ) -> dict[int, str | None]:
        if not provider_ids:
            return {}

        rows = (
            await self.db.execute(
                select(AIProvider.id, AIProvider.icon).where(
                    AIProvider.id.in_(provider_ids)
                )
            )
        ).all()
        return {row.id: row.icon for row in rows}
