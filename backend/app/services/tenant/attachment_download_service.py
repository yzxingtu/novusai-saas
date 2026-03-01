from __future__ import annotations

from datetime import timedelta
from typing import Any

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import ConfigService
from app.core.config import settings
from app.core.i18n import _
from app.enums import ErrorCode
from app.enums.attachment import AttachmentVisibility
from app.exceptions import BusinessException, NotFoundException, StorageNotFoundError
from app.models.tenant.attachment import Attachment
from app.repositories.tenant.attachment_repository import AttachmentRepository
from app.storage import StorageConfig, StorageVisibility, storage_manager
from app.core.base_model import utc_now


class AttachmentDownloadService:
    """
    附件下载/预览服务
    
    负责生成访问链接、签名控制、权限校验与下载统计。
    """
    def __init__(self, db: AsyncSession, tenant_id: int | None = None):
        """初始化服务，tenant_id 为空表示公共访问上下文"""
        self.db = db
        self.tenant_id = tenant_id
        self.config_service = ConfigService(db)
        self.repo = (
            AttachmentRepository(db, tenant_id) if tenant_id is not None else None
        )

    async def get_attachment(self, attachment_id: int) -> Attachment:
        """按租户上下文读取附件并进行归属校验"""
        if self.repo:
            attachment = await self.repo.get_by_id(attachment_id)
        else:
            result = await self.db.execute(
                select(Attachment).where(
                    Attachment.id == attachment_id,
                    Attachment.is_deleted.is_(False),
                )
            )
            attachment = result.scalar_one_or_none()
        if not attachment:
            raise NotFoundException(message=_("error.common.not_found"))
        if self.tenant_id is not None and attachment.tenant_id != self.tenant_id:
            raise BusinessException(
                message=_("error.auth.forbidden"),
                code=ErrorCode.FORBIDDEN,
            )
        return attachment

    async def build_access_url(
        self,
        attachment: Attachment,
        expires: int,
        preview: bool,
    ) -> dict[str, Any]:
        """生成访问 URL 并记录下载统计"""
        expires = self._normalize_expires(expires)
        url = await self._get_access_url(attachment, expires, preview)
        await self._record_download(attachment, attachment.size)
        return {
            "attachment_id": attachment.id,
            "url": url,
            "expires_in": expires,
            "preview": preview,
        }

    async def get_download_response(self, attachment: Attachment, preview: bool):
        """生成本地流式下载/预览响应"""
        storage_config = await self._resolve_storage_config_for_attachment(attachment)
        driver = storage_manager.get_driver(storage_config)
        filename = attachment.original_name or attachment.name
        response = await driver.get_download_response(attachment.path, filename=filename)
        if preview:
            response.headers["Content-Disposition"] = f'inline; filename="{filename}"'
        return response

    async def record_download(self, attachment: Attachment, size: int | None = None) -> None:
        """显式记录下载统计"""
        await self._record_download(attachment, size or attachment.size)

    async def get_redirect_url(
        self,
        attachment: Attachment,
        expires: int,
        preview: bool,
    ) -> str:
        """生成访问 URL（对象存储使用签名 URL）并记录下载统计"""
        expires = self._normalize_expires(expires)
        url = await self._get_access_url(attachment, expires, preview)
        await self._record_download(attachment, attachment.size)
        return url

    def create_access_token(
        self,
        attachment: Attachment,
        expires: int,
        preview: bool,
    ) -> str:
        """生成本地私有文件访问 Token"""
        expire_at = utc_now() + timedelta(seconds=expires)
        payload = {
            "type": "attachment_download",
            "attachment_id": attachment.id,
            "tenant_id": attachment.tenant_id,
            "preview": preview,
            "exp": expire_at,
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def verify_access_token(self, token: str) -> dict[str, Any]:
        """校验下载 Token 并返回 payload"""
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
        except JWTError as exc:
            raise BusinessException(
                message=_("error.auth.token_invalid"),
                code=ErrorCode.TOKEN_INVALID,
            ) from exc
        if payload.get("type") != "attachment_download":
            raise BusinessException(
                message=_("error.auth.token_invalid"),
                code=ErrorCode.TOKEN_INVALID,
            )
        return payload

    async def validate_access(
        self,
        attachment: Attachment,
        token: str | None,
    ) -> None:
        """
        校验访问权限
        - 公开文件：直接放行
        - 本地私有文件：放行（本地文件通过 API 端点提供，无法直接访问磁盘路径）
        - 远程私有文件（S3 等）：需有效签名 Token
        """
        if attachment.visibility == AttachmentVisibility.PUBLIC.value:
            return
        if attachment.driver == "local":
            return
        if not token:
            raise BusinessException(
                message=_("error.auth.unauthorized"),
                code=ErrorCode.UNAUTHORIZED,
            )
        payload = self.verify_access_token(token)
        if payload.get("attachment_id") != attachment.id:
            raise BusinessException(
                message=_("error.auth.token_invalid"),
                code=ErrorCode.TOKEN_INVALID,
            )
        if payload.get("tenant_id") != attachment.tenant_id:
            raise BusinessException(
                message=_("error.auth.token_invalid"),
                code=ErrorCode.TOKEN_INVALID,
            )

    async def _get_access_url(
        self,
        attachment: Attachment,
        expires: int,
        preview: bool,
    ) -> str:
        """按存储驱动生成访问 URL

        Resolution chain (attachment self-describing priority):
        1. local → API proxy endpoint
        2. cloud + matching config → signed/direct URL via driver
        3. cloud + public + has base_url → direct CDN URL from stored base_url
        4. fallback → API proxy endpoint
        """
        # Local: always through API proxy
        if attachment.driver == "local":
            token = None
            if attachment.visibility == AttachmentVisibility.PRIVATE.value:
                token = self.create_access_token(attachment, expires, preview)
            return self._build_public_access_url(attachment.id, token, preview)

        # Cloud: try to resolve a matching config for proper signed URL
        try:
            storage_config = await self._resolve_storage_config_for_attachment(attachment)
            if storage_config.driver == attachment.driver:
                driver = storage_manager.get_driver(storage_config)
                visibility = StorageVisibility(attachment.visibility)
                return await driver.get_url(attachment.path, expires=expires, visibility=visibility)
        except Exception:
            pass

        # Config mismatch: use stored base_url for public cloud files
        direct_url = self._build_direct_cdn_url(attachment)
        if direct_url:
            return direct_url

        # Last resort: API proxy (private file with no matching config)
        return self._build_public_access_url(attachment.id, None, preview)

    async def _resolve_storage_config_for_attachment(
        self, attachment: Attachment
    ) -> StorageConfig:
        """解析附件所属的实际存储配置（委托给统一 StorageConfigResolver）"""
        from app.services.common.storage_config_resolver import StorageConfigResolver

        resolver = StorageConfigResolver(self.db)
        return await resolver.resolve_for_attachment(
            driver=attachment.driver,
            tenant_id=self.tenant_id or 0,
        )

    @staticmethod
    def _build_direct_cdn_url(attachment: Attachment) -> str | None:
        """Build a direct CDN URL from the attachment's own stored data.

        Each attachment records its base_url at upload time. For public
        cloud files this URL remains valid even after the platform/tenant
        switches to a different storage driver.

        Returns:
            Direct URL string, or None if not possible (local, no base_url, private).
        """
        if attachment.driver == "local":
            return None
        if attachment.visibility != AttachmentVisibility.PUBLIC.value:
            return None
        base_url = attachment.base_url
        if not base_url:
            return None
        path = attachment.path.lstrip("/")
        return f"{base_url.rstrip('/')}/{path}"

    async def _record_download(self, attachment: Attachment, size: int) -> None:
        """写入下载统计到附件 meta"""
        meta = attachment.meta or {}
        count = int(meta.get("download_count", 0)) + 1
        total_bytes = int(meta.get("download_bytes", 0)) + max(0, int(size))
        meta["download_count"] = count
        meta["download_bytes"] = total_bytes
        repo = self.repo or AttachmentRepository(self.db, attachment.tenant_id)
        await repo.update(attachment.id, {"meta": meta})

    def _build_public_access_url(
        self, attachment_id: int, token: str | None, preview: bool
    ) -> str:
        """拼装公开访问 URL（本地私有文件附带 token）"""
        url = f"/api/public/attachments/{attachment_id}/access"
        params = []
        if token:
            params.append(f"token={token}")
        if preview:
            params.append("preview=1")
        if params:
            url = f"{url}?{'&'.join(params)}"
        return url

    def _normalize_expires(self, expires: int) -> int:
        """限制签名有效期范围（60s~86400s）"""
        if expires <= 0:
            return 3600
        return max(60, min(expires, 86400))


__all__ = ["AttachmentDownloadService"]
