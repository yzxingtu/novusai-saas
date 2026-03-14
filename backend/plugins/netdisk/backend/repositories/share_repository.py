"""
分享链接 Repository
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.base_repository import TenantRepository

if TYPE_CHECKING:
    from ..models.share import Share


class ShareRepository(TenantRepository["Share"]):

    async def get_by_token(self, token: str) -> Share | None:
        """按 share_token 查询（公开访问，不限企业）"""
        from ..models.share import Share
        result = await self.db.execute(
            select(Share).where(Share.share_token == token, Share.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def list_by_node(self, node_id: int) -> list[Share]:
        """节点的所有活跃分享"""
        from ..models.share import Share
        result = await self.db.execute(
            select(Share).where(
                Share.node_id == node_id,
                Share.tenant_id == self.tenant_id,
                Share.is_active.is_(True),
            ).order_by(Share.created_at.desc())
        )
        return list(result.scalars().all())
