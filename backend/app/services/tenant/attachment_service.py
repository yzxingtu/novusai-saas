"""
附件上传服务 / Attachment Upload Service

提供统一上传、分片上传、断点续传等能力
Provides unified upload, chunked upload, resumable upload capabilities.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, BinaryIO

import anyio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.configs.service import PLATFORM_TENANT_ID, ConfigService
from app.core.base_model import utc_now
from app.core.base_service import TenantService
from app.core.i18n import _
from app.enums import ErrorCode
from app.enums.attachment import (
    AttachmentSource,
    AttachmentStatus,
    AttachmentVisibility,
)
from app.exceptions import BusinessException, NotFoundException
from app.models.tenant.attachment import Attachment
from app.models.tenant.tenant import Tenant
from app.repositories.tenant.attachment_repository import AttachmentRepository
from app.services.common.file_validator import FileValidator, validate_result_or_raise
from app.services.common.storage_config_resolver import (
    StorageConfigResolver,
    merge_attachment_storage_snapshot,
)
from app.services.tenant.attachment_download_service import AttachmentDownloadService
from app.services.tenant.quota_service import QuotaService
from app.storage import StorageConfig, StorageVisibility, storage_manager

ProgressCallback = Callable[[dict[str, Any]], Any]


class AttachmentService(TenantService[Attachment, AttachmentRepository]):
    """
    附件上传服务 / Attachment upload service.
    """

    model = Attachment
    repository_class = AttachmentRepository

    def __init__(self, db: AsyncSession, tenant_id: int):
        """
        初始化服务 / Initialize service.
        """
        super().__init__(db, tenant_id)
        self._config_service = ConfigService(db)
        self._file_validator = FileValidator(db)

    @staticmethod
    def _build_client_access_url(attachment: Attachment) -> str:
        tenant_id = (
            attachment.tenant_id
            if attachment.tenant_id is not None
            else PLATFORM_TENANT_ID
        )
        return AttachmentDownloadService.build_client_access_url(
            attachment_id=attachment.id,
            tenant_id=tenant_id,
            visibility=attachment.visibility,
        )

    async def upload_file(
        self,
        content: BinaryIO,
        filename: str,
        file_size: int | None = None,
        mime_type: str | None = None,
        visibility: AttachmentVisibility = AttachmentVisibility.PRIVATE,
        source: AttachmentSource = AttachmentSource.TENANT_ADMIN,
        uploader_id: int | None = None,
        business_type: str | None = None,
        business_id: int | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """
        统一上传入口 / Unified upload entry.
        """
        await self._ensure_upload_enabled()
        # 验证文件类型 / Validate file type
        validation_result = await self._file_validator.validate_for_tenant(
            self.tenant_id, filename, file_size
        )
        validate_result_or_raise(validation_result)

        (
            storage_mode,
            storage_config,
            _apply_quota,
        ) = await self._resolve_storage_context()
        temp_path, size, file_hash = await self._save_to_temp(content)
        actual_size = file_size or size

        # 检查配额 / Check quota
        await self._check_quota(actual_size)
        # Hash de-duplication must stay visibility-scoped; public/private records cannot be reused interchangeably. / 秒传按可见性隔离 / hash dedupe visibility scoped
        existing = await self.repo.get_by_hash(
            file_hash,
            driver=storage_config.driver,
            visibility=visibility.value,
        )
        if existing:
            await self._remove_temp_file(temp_path)
            return {
                "attachment": existing,
                "url": self._build_client_access_url(existing),
                "used_bytes": await self.repo.sum_size(),
            }

        storage_path = self._build_storage_path(filename, storage_mode)
        upload_result = await self._upload_to_storage(
            storage_config=storage_config,
            storage_path=storage_path,
            temp_path=temp_path,
            mime_type=mime_type,
            visibility=visibility,
            metadata=metadata,
        )
        attachment = await self._create_attachment(
            filename=filename,
            storage_path=storage_path,
            upload_result=upload_result,
            visibility=visibility,
            source=source,
            uploader_id=uploader_id,
            business_type=business_type,
            business_id=business_id,
            metadata=metadata,
            storage_config=storage_config,
            storage_scope="platform" if storage_mode == "platform" else "tenant",
        )
        used_bytes = await self.repo.sum_size()
        url = self._build_client_access_url(attachment)
        return {"attachment": attachment, "url": url, "used_bytes": used_bytes}

    async def preflight_check(
        self,
        file_hash: str,
        filename: str,
        size: int,
        visibility: AttachmentVisibility = AttachmentVisibility.PRIVATE,
    ) -> dict[str, Any]:
        """
        预检查文件是否已存在（秒传）/ Pre-check file existence (instant upload).

        前端先计算 SHA-256 哈希，发送到此方法检查。
        如果同企业、同驱动下已存在相同哈希的文件，返回已有记录（零上传）。

        Args:
            file_hash: 文件哈希（纯 hex digest，不含 sha256: 前缀）
            filename: 文件名（用于验证文件类型）
            size: 文件大小（用于验证配额）
            visibility: 可见性

        Returns:
            {"exists": bool, "attachment": Attachment|None, "url": str|None, "used_bytes": int|None}
        """
        await self._ensure_upload_enabled()

        validation_result = await self._file_validator.validate_for_tenant(
            self.tenant_id, filename, size
        )
        validate_result_or_raise(validation_result)

        (
            _storage_mode,
            storage_config,
            _apply_quota,
        ) = await self._resolve_storage_context()
        existing = await self.repo.get_by_hash(
            file_hash,
            driver=storage_config.driver,
            visibility=visibility.value,
        )
        if existing:
            return {
                "exists": True,
                "attachment": existing,
                "url": self._build_client_access_url(existing),
                "used_bytes": await self.repo.sum_size(),
            }

        # 文件不存在时才检查配额（秒传不消耗新空间） / Check quota only when file is new (instant upload uses no extra space)
        await self._check_quota(size)
        return {
            "exists": False,
            "attachment": None,
            "url": None,
            "used_bytes": None,
        }

    async def start_chunk_upload(
        self,
        filename: str,
        total_size: int,
        chunk_size: int,
        mime_type: str | None = None,
        visibility: AttachmentVisibility = AttachmentVisibility.PRIVATE,
        source: AttachmentSource = AttachmentSource.TENANT_ADMIN,
        uploader_id: int | None = None,
        business_type: str | None = None,
        business_id: int | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """
        初始化分片上传会话 / Initialize chunk upload session.
        """
        await self._ensure_upload_enabled()
        # 验证文件类型 / Validate file type
        validation_result = await self._file_validator.validate_for_tenant(
            self.tenant_id, filename, total_size
        )
        validate_result_or_raise(validation_result)

        if total_size <= 0 or chunk_size <= 0:
            raise BusinessException(
                message=_("error.common.invalid_parameter"),
                code=ErrorCode.INVALID_PARAMETER,
            )
        storage_mode = await self._get_storage_mode()
        await self._check_quota(total_size)

        upload_id = uuid.uuid4().hex
        session = {
            "upload_id": upload_id,
            "tenant_id": self.tenant_id,
            "storage_mode": storage_mode,
            "filename": filename,
            "total_size": total_size,
            "chunk_size": chunk_size,
            "chunk_count": self._calc_chunk_count(total_size, chunk_size),
            "mime_type": mime_type,
            "visibility": visibility.value,
            "source": source.value,
            "uploader_id": uploader_id,
            "business_type": business_type,
            "business_id": business_id,
            "metadata": metadata or {},
            "uploaded_chunks": [],
            "created_at": utc_now().isoformat(),
        }
        await self._save_session(session)
        return self._build_session_response(session, uploaded_bytes=0)

    async def upload_chunk(
        self,
        upload_id: str,
        chunk_index: int,
        content: BinaryIO,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """
        上传分片 / Upload chunk.
        """
        await self._ensure_chunk_upload_entitled()
        session = await self._load_session(upload_id)
        chunk_count = int(session["chunk_count"])
        if chunk_index < 0 or chunk_index >= chunk_count:
            raise BusinessException(
                message=_("error.common.invalid_parameter"),
                code=ErrorCode.INVALID_PARAMETER,
            )

        chunk_path = self._get_chunk_path(upload_id, chunk_index)
        await self._write_chunk(chunk_path, content)

        uploaded_chunks = set(session.get("uploaded_chunks", []))
        uploaded_chunks.add(chunk_index)
        session["uploaded_chunks"] = sorted(uploaded_chunks)

        uploaded_bytes = await self._calc_uploaded_bytes(
            upload_id, session["uploaded_chunks"]
        )
        response = self._build_session_response(session, uploaded_bytes=uploaded_bytes)

        if progress_callback:
            await self._trigger_progress(progress_callback, response)

        await self._save_session(session)
        return response

    async def complete_chunk_upload(self, upload_id: str) -> dict[str, Any]:
        """
        完成分片上传并合并文件 / Complete chunk upload and merge files.
        """
        await self._ensure_chunk_upload_entitled()
        session = await self._load_session(upload_id)
        chunk_count = int(session["chunk_count"])
        uploaded_chunks = set(session.get("uploaded_chunks", []))
        if len(uploaded_chunks) != chunk_count:
            raise BusinessException(
                message=_("error.common.invalid_parameter"),
                code=ErrorCode.INVALID_PARAMETER,
            )

        temp_path, size, file_hash = await self._merge_chunks(upload_id, chunk_count)
        storage_mode = session.get("storage_mode", "platform")
        await self._check_quota(size)
        storage_config = await self._resolve_storage_config(storage_mode)

        existing = await self.repo.get_by_hash(
            file_hash,
            driver=storage_config.driver,
            visibility=str(session["visibility"]),
        )
        if existing:
            await self._remove_temp_file(temp_path)
            await self._remove_session(upload_id)
            return {
                "attachment": existing,
                "url": self._build_client_access_url(existing),
                "used_bytes": await self.repo.sum_size(),
            }

        storage_path = self._build_storage_path(session["filename"], storage_mode)
        upload_result = await self._upload_to_storage(
            storage_config=storage_config,
            storage_path=storage_path,
            temp_path=temp_path,
            mime_type=session.get("mime_type"),
            visibility=AttachmentVisibility(session["visibility"]),
            metadata=session.get("metadata"),
        )
        attachment = await self._create_attachment(
            filename=session["filename"],
            storage_path=storage_path,
            upload_result=upload_result,
            visibility=AttachmentVisibility(session["visibility"]),
            source=AttachmentSource(session["source"]),
            uploader_id=session.get("uploader_id"),
            business_type=session.get("business_type"),
            business_id=session.get("business_id"),
            metadata=session.get("metadata"),
            storage_config=storage_config,
            storage_scope="platform" if storage_mode == "platform" else "tenant",
        )
        await self._remove_session(upload_id)
        used_bytes = await self.repo.sum_size()
        url = self._build_client_access_url(attachment)
        return {"attachment": attachment, "url": url, "used_bytes": used_bytes}

    async def get_upload_status(self, upload_id: str) -> dict[str, Any]:
        """
        获取分片上传进度 / Get chunk upload progress.
        """
        session = await self._load_session(upload_id)
        uploaded_bytes = await self._calc_uploaded_bytes(
            upload_id, session.get("uploaded_chunks", [])
        )
        return self._build_session_response(session, uploaded_bytes=uploaded_bytes)

    async def abort_upload(self, upload_id: str) -> None:
        """
        取消上传并清理临时文件 / Abort upload and clean temp files.
        """
        await self._remove_session(upload_id)

    async def _ensure_upload_enabled(self) -> None:
        """
        检查企业上传功能开关 / Check tenant upload feature flag.
        """
        enabled = await self._config_service.get_tenant_config(
            self.tenant_id,
            "tenant_file_upload",
            default=True,
        )
        if not enabled:
            raise BusinessException(
                message=_("error.auth.forbidden"),
                code=ErrorCode.FORBIDDEN,
            )

    async def _ensure_chunk_upload_entitled(self) -> None:
        """
        写入临时分片前重新检查上传资格 / Re-check upload entitlement before temporary chunk writes.

        分片会话可能跨过套餐降级；每次写入仍必须要求有效套餐，避免停用租户继续占用临时存储。
        Chunk sessions can outlive a downgrade; each write still requires an
        active plan so disabled tenants cannot keep filling temporary storage.
        """
        await self._ensure_upload_enabled()
        tenant = await self._get_tenant()
        quota_service = QuotaService(self.db, tenant)
        storage_check = await quota_service.check_storage_quota(
            additional_bytes=0,
            current_bytes=0,
        )
        if not storage_check.allowed:
            raise BusinessException(
                message=storage_check.message or _("quota.storage_exceeded"),
                code=ErrorCode.FORBIDDEN,
            )

    async def _check_quota(self, additional_bytes: int) -> None:
        """
        检查文件大小与存储配额 / Check file size and storage quota.

        - 单文件大小限制：取 min(套餐 max_file_size_mb, 系统配置 platform_storage_max_file_size_mb)
        - 存储总量配额（storage_limit_gb）：全局生效，不管存储到哪里
        """
        tenant = await self._get_tenant()
        quota_service = QuotaService(self.db, tenant)

        # 单文件大小：取套餐和系统配置中更严格的那个 / Per-file size: stricter of plan vs system config
        plan_limit_mb = quota_service.get_quota_value("max_file_size_mb", 0)

        from app.configs.service import ConfigService

        config_service = ConfigService(self.db)
        platform_limit_mb = int(
            await config_service.get_platform_config(
                "platform_storage_max_file_size_mb",
                default=100,
            )
            or 100
        )

        # 确定有效限制（0 表示无限制，取非零中更小的） / Resolve effective limit (0 = unlimited; pick min non-zero)
        limits = [v for v in (plan_limit_mb, platform_limit_mb) if v > 0]
        effective_limit_mb = min(limits) if limits else 0

        if effective_limit_mb > 0:
            file_size_mb = additional_bytes / (1024 * 1024)
            if file_size_mb > effective_limit_mb:
                raise BusinessException(
                    message=_("file.file_too_large"),
                    code=ErrorCode.INVALID_PARAMETER,
                    detail=f"File size {file_size_mb:.1f}MB exceeds limit {effective_limit_mb}MB",
                )

        # 存储总量全局检查 / Storage total quota check
        current_bytes = await self.repo.sum_size()
        storage_check = await quota_service.check_storage_quota(
            additional_bytes=additional_bytes,
            current_bytes=current_bytes,
        )
        if not storage_check.allowed:
            raise BusinessException(
                message=storage_check.message or _("quota.storage_exceeded"),
                code=ErrorCode.CONFLICT,
            )

    async def _get_tenant(self) -> Tenant:
        """
        获取企业信息（含套餐）/ Get tenant with plan.
        """
        result = await self.db.execute(
            select(Tenant)
            .options(selectinload(Tenant.tenant_plan))
            .where(Tenant.id == self.tenant_id, Tenant.is_deleted.is_(False))
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise NotFoundException(message=_("tenant.not_found"))
        return tenant

    async def _save_to_temp(self, content: BinaryIO) -> tuple[str, int, str]:
        """
        将内容写入临时文件并计算哈希 / Write content to temp file and compute hash.
        """

        def _write() -> tuple[str, int, str]:
            size = 0
            hasher = hashlib.sha256()
            with tempfile.NamedTemporaryFile(delete=False) as temp:
                while True:
                    chunk = content.read(8192)
                    if not chunk:
                        break
                    temp.write(chunk)
                    hasher.update(chunk)
                    size += len(chunk)
                return temp.name, size, hasher.hexdigest()

        return await anyio.to_thread.run_sync(_write)

    async def _remove_temp_file(self, temp_path: str) -> None:
        """
        删除临时文件 / Remove temp file.
        """

        def _remove() -> None:
            Path(temp_path).unlink(missing_ok=True)

        await anyio.to_thread.run_sync(_remove)

    async def _upload_to_storage(
        self,
        storage_config: StorageConfig,
        storage_path: str,
        temp_path: str,
        mime_type: str | None,
        visibility: AttachmentVisibility,
        metadata: dict | None,
    ):
        """
        上传临时文件到存储驱动 / Upload temp file to storage driver.
        """
        driver = storage_manager.get_driver(storage_config)
        with open(temp_path, "rb") as f:
            upload_result = await driver.put(
                storage_path,
                f,
                mime_type=mime_type,
                visibility=StorageVisibility(visibility.value),
                metadata=metadata,
            )
        await self._remove_temp_file(temp_path)
        return upload_result

    async def _create_attachment(
        self,
        filename: str,
        storage_path: str,
        upload_result,
        visibility: AttachmentVisibility,
        source: AttachmentSource,
        uploader_id: int | None,
        business_type: str | None,
        business_id: int | None,
        metadata: dict | None,
        storage_config: StorageConfig | None = None,
        storage_scope: str | None = None,
    ) -> Attachment:
        """
        落库附件记录 / Persist attachment record.
        """
        extension = Path(filename).suffix.lstrip(".") if filename else None

        # 获取 base_url
        if storage_config:
            driver = storage_manager.get_driver(storage_config)
            base_url = driver.get_base_url()
        else:
            # 容错处理：如果没有 storage_config，使用空字符串
            base_url = ""
        stored_meta = metadata or {}
        if storage_config and storage_scope in {"platform", "tenant"}:
            stored_meta = merge_attachment_storage_snapshot(
                metadata,
                storage_config,
                storage_scope,
            )

        attachment = await self.repo.create(
            {
                "name": filename or Path(storage_path).name,
                "original_name": filename,
                "path": storage_path,
                "size": upload_result.size,
                "hash": upload_result.hash,
                "mime_type": upload_result.mime_type,
                "extension": extension,
                "visibility": visibility.value,
                "driver": upload_result.driver,
                "base_url": base_url,
                "status": AttachmentStatus.ACTIVE.value,
                "source": source.value,
                "uploader_id": uploader_id,
                "business_type": business_type,
                "business_id": business_id,
                "meta": stored_meta,
            }
        )
        return attachment

    async def _resolve_storage_context(self) -> tuple[str, StorageConfig, bool]:
        from app.services.common.storage_config_resolver import StorageConfigResolver

        resolver = StorageConfigResolver(self.db)
        return await resolver.resolve_context(self.tenant_id)

    async def _get_storage_mode(self) -> str:
        from app.services.common.storage_config_resolver import StorageConfigResolver

        resolver = StorageConfigResolver(self.db)
        return await resolver.get_storage_mode(self.tenant_id)

    async def _resolve_storage_config(self, storage_mode: str) -> StorageConfig:
        """
        解析存储配置（委托给统一 StorageConfigResolver）/ Resolve storage config (via StorageConfigResolver).
        """
        from app.services.common.storage_config_resolver import StorageConfigResolver

        resolver = StorageConfigResolver(self.db)
        return await resolver.resolve_config(storage_mode, self.tenant_id)

    def _build_storage_path(self, filename: str, storage_mode: str = "platform") -> str:
        """
        构建存储路径 / Build storage path.

        Mode 1 (platform / shared bucket): tenants/{tenant_id}/{date}/{uuid}.ext
        Mode 2/3 (tenant independent bucket): {date}/{uuid}.ext
        """
        suffix = Path(filename).suffix if filename else ""
        date_path = utc_now().strftime("%Y/%m/%d")
        unique = uuid.uuid4().hex
        if storage_mode == "platform":
            return f"tenants/{self.tenant_id}/{date_path}/{unique}{suffix}"
        return f"{date_path}/{unique}{suffix}"

    def _get_upload_root(self) -> Path:
        """
        获取上传临时根目录 / Get upload temp root.
        """
        return Path(tempfile.gettempdir()) / "novusai_uploads" / str(self.tenant_id)

    def _get_session_path(self, upload_id: str) -> Path:
        """
        获取上传会话路径 / Get upload session path.
        """
        return self._get_upload_root() / upload_id

    def _get_session_file(self, upload_id: str) -> Path:
        """
        获取会话状态文件 / Get session state file.
        """
        return self._get_session_path(upload_id) / "session.json"

    def _get_chunk_path(self, upload_id: str, chunk_index: int) -> Path:
        """
        获取分片文件路径 / Get chunk file path.
        """
        return self._get_session_path(upload_id) / f"{chunk_index}.part"

    async def _save_session(self, session: dict[str, Any]) -> None:
        """
        保存会话状态 / Save session state.
        """
        session_path = self._get_session_path(session["upload_id"])
        session_path.mkdir(parents=True, exist_ok=True)
        session_file = session_path / "session.json"

        def _write() -> None:
            session_file.write_text(
                json.dumps(session, ensure_ascii=False), encoding="utf-8"
            )

        await anyio.to_thread.run_sync(_write)

    async def _load_session(self, upload_id: str) -> dict[str, Any]:
        """
        加载会话状态（含企业隔离校验）/ Load session (with tenant isolation check).
        """
        session_file = self._get_session_file(upload_id)
        if not session_file.exists():
            raise BusinessException(
                message=_("error.common.not_found"),
                code=ErrorCode.NOT_FOUND,
            )

        def _read() -> dict[str, Any]:
            return json.loads(session_file.read_text(encoding="utf-8"))

        session = await anyio.to_thread.run_sync(_read)

        # 企业隔离校验：确保当前企业只能操作自己的上传会话 / Tenant isolation: only this tenant may touch its upload sessions
        session_tenant_id = session.get("tenant_id")
        if session_tenant_id is not None and int(session_tenant_id) != self.tenant_id:
            raise BusinessException(
                message=_("error.auth.forbidden"),
                code=ErrorCode.FORBIDDEN,
            )

        return session

    async def _remove_session(self, upload_id: str) -> None:
        """
        删除会话及分片文件 / Remove session and chunk files.
        """
        session_path = self._get_session_path(upload_id)

        def _remove() -> None:
            if session_path.exists():
                for item in session_path.iterdir():
                    item.unlink(missing_ok=True)
                session_path.rmdir()

        await anyio.to_thread.run_sync(_remove)

    async def _write_chunk(self, chunk_path: Path, content: BinaryIO) -> None:
        """
        写入分片文件 / Write chunk file.
        """
        chunk_path.parent.mkdir(parents=True, exist_ok=True)

        def _write() -> None:
            with open(chunk_path, "wb") as f:
                while True:
                    chunk = content.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)

        await anyio.to_thread.run_sync(_write)

    async def _calc_uploaded_bytes(self, upload_id: str, chunks: list[int]) -> int:
        """
        计算已上传字节数 / Calculate uploaded bytes.
        """

        def _sum() -> int:
            total = 0
            for chunk_index in chunks:
                chunk_path = self._get_chunk_path(upload_id, chunk_index)
                if chunk_path.exists():
                    total += chunk_path.stat().st_size
            return total

        return await anyio.to_thread.run_sync(_sum)

    async def _merge_chunks(
        self, upload_id: str, chunk_count: int
    ) -> tuple[str, int, str]:
        """
        合并分片并计算哈希 / Merge chunks and compute hash.
        """

        def _merge() -> tuple[str, int, str]:
            size = 0
            hasher = hashlib.sha256()
            with tempfile.NamedTemporaryFile(delete=False) as temp:
                for index in range(chunk_count):
                    chunk_path = self._get_chunk_path(upload_id, index)
                    with open(chunk_path, "rb") as f:
                        while True:
                            chunk = f.read(8192)
                            if not chunk:
                                break
                            temp.write(chunk)
                            hasher.update(chunk)
                            size += len(chunk)
                return temp.name, size, hasher.hexdigest()

        return await anyio.to_thread.run_sync(_merge)

    def _calc_chunk_count(self, total_size: int, chunk_size: int) -> int:
        """
        计算分片数量 / Calculate chunk count.
        """
        if chunk_size <= 0:
            return 0
        return (total_size + chunk_size - 1) // chunk_size

    def _build_session_response(
        self, session: dict[str, Any], uploaded_bytes: int
    ) -> dict[str, Any]:
        """
        构建会话响应 / Build session response.
        """
        total_size = int(session["total_size"])
        percent = int(uploaded_bytes * 100 / total_size) if total_size else 0
        return {
            "upload_id": session["upload_id"],
            "filename": session["filename"],
            "total_size": total_size,
            "chunk_size": int(session["chunk_size"]),
            "chunk_count": int(session["chunk_count"]),
            "uploaded_chunks": session.get("uploaded_chunks", []),
            "uploaded_bytes": uploaded_bytes,
            "progress": percent,
        }

    async def _trigger_progress(
        self, callback: ProgressCallback, payload: dict[str, Any]
    ) -> None:
        """
        触发进度回调 / Invoke progress callback.
        """
        result = callback(payload)
        if hasattr(result, "__await__"):
            await result

    # ========================================
    # 附件管理方法 / Attachment admin methods
    # ========================================

    async def delete(self, id: int, soft: bool = True) -> bool:
        """
        删除附件（含依赖检查 + 物理文件删除）/ Delete attachment (dependency check + physical delete).

        流程：
        1. 获取附件信息（driver / path / tenant_id）
        2. 调用 BaseService.delete() 执行 __delete_deps__ 检查与软删除
        3. 删除存储中的物理文件（本地 / 七牛 / S3 等）

        Args:
            id: 附件 ID
            soft: 是否软删除（默认 True）

        Returns:
            是否删除成功
        """
        attachment = await self.repo.get_by_id(id)
        if not attachment:
            raise NotFoundException(message=_("error.common.not_found"))

        # 保存物理文件信息（删除后 instance 可能不可用）
        file_driver = attachment.driver
        file_path = attachment.path
        file_tenant_id = attachment.tenant_id or PLATFORM_TENANT_ID

        # BaseService.delete() 自动执行 __delete_deps__ 检查
        result = await super().delete(id, soft=soft)

        if result:
            await self._delete_storage_file(file_driver, file_path, file_tenant_id)

        return result

    async def _delete_storage_file(
        self, driver_name: str, path: str, tenant_id: int
    ) -> None:
        """
        从存储驱动中删除物理文件 / Delete physical file from storage driver.

        Args:
            driver_name: 存储驱动名称（local / qiniu / s3 等）
            path: 文件存储路径
            tenant_id: 企业 ID（用于解析存储配置）
        """
        from app.core.logging import LogManager

        logger = LogManager.get_logger("storage")
        try:
            resolver = StorageConfigResolver(self.db)
            config = await resolver.resolve_for_attachment(driver_name, tenant_id)
            driver = storage_manager.get_driver(config)
            deleted = await driver.delete(path)
            if deleted:
                logger.info(
                    "Storage file deleted: driver={} path={}",
                    driver_name,
                    path,
                )
            else:
                logger.warning(
                    "Storage file not found (already removed?): driver={} path={}",
                    driver_name,
                    path,
                )
        except Exception as e:
            logger.error(
                "Failed to delete storage file: driver={} path={} error={}",
                driver_name,
                path,
                str(e),
            )

    async def get_storage_stats(self) -> dict[str, Any]:
        """
        获取企业存储统计 / Get tenant storage stats.

        Returns:
            存储统计信息
        """
        total_size = await self.repo.sum_size()
        total_count = await self.repo.count()
        return {
            "total_size": total_size,
            "total_count": total_count,
        }

    async def get_used_storage_bytes(self) -> int:
        """获取已使用存储字节数 / Get used storage bytes."""
        return await self.repo.sum_size()


__all__ = ["AttachmentService"]
