"""分享链接 Service — bcrypt 密码 + secrets token / Share link service — bcrypt password and secrets token."""

from __future__ import annotations

import secrets

import bcrypt

from app.core.base_service import TenantService
from app.core.i18n import _
from app.exceptions import BusinessException, NotFoundException


class ShareService(TenantService):
    def __init__(self, db, tenant_id: int | None):
        # This service composes repositories on demand and does not rely on BaseService.repo.
        self.db = db
        self.tenant_id = tenant_id

    async def create_share(
        self,
        node_id: int,
        permission: str = "download",
        password: str | None = None,
        expires_days: int | None = None,
    ) -> object:
        from datetime import timedelta

        from app.core.base_model import utc_now
        from ..models.share import Share
        from ..repositories.node_repository import NodeRepository

        # 校验节点存在且属于当前企业
        node_repo = NodeRepository(self.db, self.tenant_id)
        node = await node_repo.get(node_id)
        if node is None or node.tenant_id != self.tenant_id or node.is_deleted:
            raise NotFoundException(message=_("plugin.netdisk.error.node_not_found"))

        password_hash = None
        if password:
            password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        expires_at = None
        if expires_days and expires_days > 0:
            expires_at = utc_now() + timedelta(days=expires_days)

        share = Share(
            tenant_id=self.tenant_id,
            node_id=node_id,
            share_token=secrets.token_urlsafe(32),
            password_hash=password_hash,
            permission=permission,
            expires_at=expires_at,
            is_active=True,
            created_by=self._current_user_id,
            created_at=utc_now(),
        )
        self.db.add(share)
        await self.db.commit()
        await self.db.refresh(share)
        return share

    async def cancel_share(self, token: str) -> None:
        from ..repositories.share_repository import ShareRepository
        repo = ShareRepository(self.db, self.tenant_id)
        share = await repo.get_by_token(token)
        if share is None or share.tenant_id != self.tenant_id:
            raise NotFoundException(message=_("plugin.netdisk.error.share_not_found"))
        share.is_active = False
        await self.db.commit()

    async def list_my_shares(self, page: int = 1, size: int = 50) -> dict:
        """当前企业的全部分享链接（分页），含文件名和类型 / All tenant share links (paged), with file name/type."""
        from sqlalchemy import func, select

        from ..models.node import FileNode
        from ..models.share import Share

        total_result = await self.db.execute(
            select(func.count(Share.id)).where(Share.tenant_id == self.tenant_id)
        )
        total = total_result.scalar_one() or 0

        result = await self.db.execute(
            select(Share, FileNode.name, FileNode.node_type)
            .outerjoin(FileNode, FileNode.id == Share.node_id)
            .where(Share.tenant_id == self.tenant_id)
            .order_by(Share.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = result.all()
        items = [
            {"share": row[0], "node_name": row[1], "node_type": row[2]}
            for row in rows
        ]
        return {"items": items, "total": total}

    async def list_node_shares(self, node_id: int) -> list:
        from ..repositories.share_repository import ShareRepository
        repo = ShareRepository(self.db, self.tenant_id)
        return await repo.list_by_node(node_id)

    # ── 公开访问（@public 端点调用）──────────────────────────

    async def access_share(self, token: str) -> object:
        """公开访问分享（不需要登录），返回节点元数据 / Access share (no login), return node metadata."""
        share = await self._get_active_share(token)
        from ..repositories.node_repository import NodeRepository
        node_repo = NodeRepository(self.db, share.tenant_id)
        node = await node_repo.get(share.node_id)
        if node is None:
            raise NotFoundException(message=_("plugin.netdisk.error.share_not_found"))
        share.increment_access()
        await self.db.commit()
        return {"share": share, "node": node}

    async def verify_password(self, token: str, password: str) -> bool:
        """验证分享密码（调用前已经 IPRateLimiter 限流） / Verify share password (rate limited by caller)."""
        share = await self._get_active_share(token)
        if share.password_hash is None:
            return True
        return bcrypt.checkpw(password.encode(), share.password_hash.encode())

    async def get_download_url(self, token: str, node_id: int) -> str:
        """获取分享文件的签名下载 URL / Get signed download URL for share file.
        安全：强制校验 node_id == share.node_id，防止 IDOR。
        """
        from app.storage.manager import StorageManager
        share = await self._get_active_share(token)
        if share.permission not in ("download",):
            raise BusinessException(message=_("plugin.netdisk.error.no_download_permission"))

        # IDOR 防护：传入的 node_id 必须与分享记录的 node_id 一致
        if node_id != share.node_id:
            raise NotFoundException(message=_("plugin.netdisk.error.node_not_found"))

        from ..repositories.node_repository import NodeRepository
        node_repo = NodeRepository(self.db, share.tenant_id)
        node = await node_repo.get(node_id)
        if node is None or not node.storage_key or node.is_deleted:
            raise NotFoundException(message=_("plugin.netdisk.error.node_not_found"))

        storage = StorageManager.get_driver()
        return await storage.get_url(node.storage_key, expires=900)  # 15 分钟

    async def _get_active_share(self, token: str):
        from ..repositories.share_repository import ShareRepository
        repo = ShareRepository(self.db, tenant_id=0)  # 公开访问，不限企业
        share = await repo.get_by_token(token)
        if share is None or not share.is_active:
            raise NotFoundException(message=_("plugin.netdisk.error.share_not_found"))
        if share.is_expired():
            raise BusinessException(
                message=_("plugin.netdisk.error.share_expired"),
                status_code=410,
            )
        return share

    # ── 管理端操作（在 Service 层查询，Controller 不直接操作 DB）─────

    async def admin_list_shares(self, page: int = 1, size: int = 20) -> dict:
        """管理端：分页列出全部企业分享记录 / Admin: list all tenant shares (paged)."""
        from sqlalchemy import func, select

        from ..models.share import Share

        total_result = await self.db.execute(select(func.count(Share.id)))
        total = total_result.scalar_one() or 0

        result = await self.db.execute(
            select(Share)
            .order_by(Share.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        items = list(result.scalars().all())
        return {"items": items, "total": total}

    async def admin_revoke_share(self, token: str) -> None:
        """管理端：强制撤销指定分享 / Admin: revoke share."""
        from ..repositories.share_repository import ShareRepository
        repo = ShareRepository(self.db, tenant_id=0)
        share = await repo.get_by_token(token)
        if share is None:
            raise NotFoundException(message=_("plugin.netdisk.error.share_not_found"))
        share.is_active = False
        await self.db.commit()

    @property
    def _current_user_id(self) -> int | None:
        return getattr(self, "_user_id", None)
