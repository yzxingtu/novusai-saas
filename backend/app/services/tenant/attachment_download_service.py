from __future__ import annotations

import hashlib
import hmac
import time
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import ConfigService, PLATFORM_TENANT_ID
from app.core.base_model import utc_now
from app.core.config import settings
from app.core.i18n import _
from app.enums import ErrorCode
from app.enums.attachment import AttachmentVisibility
from app.exceptions import BusinessException, NotFoundException
from app.models.tenant.attachment import Attachment
from app.repositories.tenant.attachment_repository import AttachmentRepository
from app.storage import StorageConfig, StorageVisibility, build_content_disposition, storage_manager


class AttachmentDownloadService:
    """
    附件下载/预览服务 / Attachment download/preview service.

    负责生成访问链接、签名控制、权限校验与下载统计。
    """
    def __init__(self, db: AsyncSession, tenant_id: int | None = None):
        """初始化服务，tenant_id 为空表示公共访问上下文 / Init service; tenant_id=None means public access context."""
        self.db = db
        self.tenant_id = tenant_id
        self.config_service = ConfigService(db)
        self.repo = (
            AttachmentRepository(db, tenant_id) if tenant_id is not None else None
        )

    async def get_attachment(self, attachment_id: int) -> Attachment:
        """按企业上下文读取附件并进行归属校验 / Load attachment by tenant context and validate ownership."""
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
        """生成访问 URL 并记录下载统计 / Build access URL and record download stats."""
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
        """生成本地流式下载/预览响应 / Build local streaming download/preview response."""
        storage_config = await self._resolve_storage_config_for_attachment(attachment)
        driver = storage_manager.get_driver(storage_config)
        filename = attachment.original_name or attachment.name
        response = await driver.get_download_response(attachment.path, filename=filename)
        if preview:
            response.headers["Content-Disposition"] = build_content_disposition(
                filename,
                disposition="inline",
            )
        return response

    async def record_download(self, attachment: Attachment, size: int | None = None) -> None:
        """显式记录下载统计 / Record download stats explicitly."""
        await self._record_download(attachment, size or attachment.size)

    async def get_redirect_url(
        self,
        attachment: Attachment,
        expires: int,
        preview: bool,
    ) -> str:
        """生成访问 URL（对象存储使用签名 URL）并记录下载统计 / Build access URL (signed for object storage) and record download."""
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
        """生成本地私有文件访问 Token / Create local private file access token."""
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
        """校验下载 Token 并返回 payload / Verify download token and return payload."""
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
        校验访问权限 / Validate access (public: allow; private: require valid signed token).
        - 公开文件：直接放行
        - 私有文件（所有驱动）：需有效签名 Token
        """
        if attachment.visibility == AttachmentVisibility.PUBLIC.value:
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
        """按存储驱动生成访问 URL / Build access URL by storage driver.

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
            return self._build_public_access_url(
                attachment.id, token, preview, expires=expires,
            )

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
        return self._build_public_access_url(
            attachment.id, None, preview, expires=expires,
        )

    async def _resolve_storage_config_for_attachment(
        self, attachment: Attachment
    ) -> StorageConfig:
        """解析附件所属的实际存储配置（委托给统一 StorageConfigResolver） / Resolve storage config for attachment (via StorageConfigResolver)."""
        from app.services.common.storage_config_resolver import StorageConfigResolver

        resolver = StorageConfigResolver(self.db)
        return await resolver.resolve_for_attachment_record(attachment)

    @staticmethod
    def _build_direct_cdn_url(attachment: Attachment) -> str | None:
        """从附件自身存储的 base_url 构建直连 CDN URL / Build a direct CDN URL from the attachment's own stored data.

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
        """写入下载统计到附件 meta / Write download stats to attachment meta."""
        meta = attachment.meta or {}
        count = int(meta.get("download_count", 0)) + 1
        total_bytes = int(meta.get("download_bytes", 0)) + max(0, int(size))
        meta["download_count"] = count
        meta["download_bytes"] = total_bytes
        repo = self.repo or AttachmentRepository(self.db, attachment.tenant_id)
        await repo.update(attachment.id, {"meta": meta})

    def _build_public_access_url(
        self, attachment_id: int, token: str | None, preview: bool,
        expires: int = 3600,
    ) -> str:
        """拼装公开访问 URL（附带 HMAC 签名防枚举 + 可选私有 token） / Build public access URL (HMAC sign + optional token)."""
        exp = int(time.time()) + expires
        sign = self.create_access_sign(attachment_id, exp)
        params: dict[str, str] = {"exp": str(exp), "sign": sign}
        if token:
            params["token"] = token
        if preview:
            params["preview"] = "1"
        return f"/api/public/attachments/{attachment_id}/access?{urlencode(params)}"

    @staticmethod
    def build_preview_url(
        attachment_id: int,
        tenant_id: int,
        visibility: str,
        expires: int = 3600,
    ) -> str:
        """为前端 <img> 生成带签名的预览 URL（无需 DB）/ Build signed preview URL for frontend <img> (no DB).

        公开文件：仅 HMAC 签名；私有文件：HMAC + JWT token.
        """
        exp_ts = int(time.time()) + expires
        sign = AttachmentDownloadService.create_access_sign(attachment_id, exp_ts)
        params: dict[str, str] = {"exp": str(exp_ts), "sign": sign}
        if visibility != AttachmentVisibility.PUBLIC.value:
            expire_at = utc_now() + timedelta(seconds=expires)
            token_payload = {
                "type": "attachment_download",
                "attachment_id": attachment_id,
                "tenant_id": tenant_id,
                "preview": True,
                "exp": expire_at,
            }
            params["token"] = jwt.encode(
                token_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM,
            )
        return f"/api/public/attachments/{attachment_id}/image?{urlencode(params)}"

    @staticmethod
    def build_client_access_url(
        attachment_id: int,
        tenant_id: int,
        visibility: str,
        expires: int = 3600,
    ) -> str:
        """Build a client-facing access URL.

        Public files keep a stable `/access` path for long-lived content such as
        rich-text links. Private files get a signed URL for immediate display/use.
        """
        if visibility == AttachmentVisibility.PUBLIC.value:
            return f"/api/public/attachments/{attachment_id}/access"

        exp_ts = int(time.time()) + expires
        sign = AttachmentDownloadService.create_access_sign(attachment_id, exp_ts)
        expire_at = utc_now() + timedelta(seconds=expires)
        token_payload = {
            "type": "attachment_download",
            "attachment_id": attachment_id,
            "tenant_id": tenant_id,
            "preview": False,
            "exp": expire_at,
        }
        params = {
            "exp": str(exp_ts),
            "sign": sign,
            "token": jwt.encode(
                token_payload,
                settings.SECRET_KEY,
                algorithm=settings.ALGORITHM,
            ),
        }
        return f"/api/public/attachments/{attachment_id}/access?{urlencode(params)}"

    @staticmethod
    def create_access_sign(attachment_id: int, exp: int) -> str:
        """HMAC-SHA256 签名：防止公开端点 ID 枚举 / HMAC-SHA256 sign to prevent ID enumeration."""
        msg = f"{attachment_id}:{exp}".encode()
        return hmac.new(
            settings.SECRET_KEY.encode(), msg, hashlib.sha256,
        ).hexdigest()[:32]

    @staticmethod
    def verify_access_sign(
        attachment_id: int, exp: int | str | None, sign: str | None,
    ) -> None:
        """校验 HMAC 签名和过期时间，无效则抛出 BusinessException / Verify HMAC and expiry; raise on invalid."""
        if not exp or not sign:
            raise BusinessException(
                message=_("error.auth.unauthorized"),
                code=ErrorCode.UNAUTHORIZED,
            )
        try:
            exp_int = int(exp)
        except (ValueError, TypeError) as exc:
            raise BusinessException(
                message=_("error.auth.token_invalid"),
                code=ErrorCode.TOKEN_INVALID,
            ) from exc
        if exp_int < time.time():
            raise BusinessException(
                message=_("error.auth.token_expired"),
                code=ErrorCode.TOKEN_EXPIRED,
            )
        expected = AttachmentDownloadService.create_access_sign(attachment_id, exp_int)
        if not hmac.compare_digest(expected, sign):
            raise BusinessException(
                message=_("error.auth.token_invalid"),
                code=ErrorCode.TOKEN_INVALID,
            )

    def _normalize_expires(self, expires: int) -> int:
        """限制签名有效期范围（60s~86400s） / Clamp signature expiry to 60s–86400s."""
        if expires <= 0:
            return 3600
        return max(60, min(expires, 86400))


__all__ = ["AttachmentDownloadService"]
