"""
附件上传服务

提供统一上传、分片上传、断点续传等能力
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Callable

import anyio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.configs.service import ConfigService
from app.core.base_service import TenantService
from app.core.i18n import _
from app.enums import ErrorCode
from app.enums.attachment import AttachmentSource, AttachmentStatus, AttachmentVisibility
from app.exceptions import BusinessException, NotFoundException
from app.models.tenant.attachment import Attachment
from app.models.tenant.tenant import Tenant
from app.repositories.tenant.attachment_repository import AttachmentRepository
from app.services.common.file_validator import FileValidator, validate_result_or_raise
from app.services.tenant.quota_service import QuotaService
from app.storage import StorageConfig, StorageVisibility, storage_manager

ProgressCallback = Callable[[dict[str, Any]], Any]


class AttachmentService(TenantService[Attachment, AttachmentRepository]):
    """
    附件上传服务
    """

    model = Attachment
    repository_class = AttachmentRepository

    def __init__(self, db: AsyncSession, tenant_id: int):
        """
        初始化服务
        """
        super().__init__(db, tenant_id)
        self._config_service = ConfigService(db)
        self._file_validator = FileValidator(db)

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
        统一上传入口
        """
        await self._ensure_upload_enabled()
        # 验证文件类型
        validation_result = await self._file_validator.validate_for_tenant(
            self.tenant_id, filename, file_size
        )
        validate_result_or_raise(validation_result)

        storage_mode, storage_config, apply_quota = await self._resolve_storage_context()
        temp_path, size, file_hash = await self._save_to_temp(content)
        actual_size = file_size or size

        # 检查配额
        await self._check_quota(actual_size, apply_quota=apply_quota)
        existing = await self.repo.get_by_hash(file_hash)
        if existing:
            await self._remove_temp_file(temp_path)
            url = await self._get_existing_url(storage_config, existing)
            return {
                "attachment": existing,
                "url": url,
                "used_bytes": await self.repo.sum_size(),
            }

        storage_path = self._build_storage_path(filename)
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
        )
        used_bytes = await self.repo.sum_size()
        return {"attachment": attachment, "url": upload_result.url, "used_bytes": used_bytes}

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
        初始化分片上传会话
        """
        await self._ensure_upload_enabled()
        # 验证文件类型
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
        apply_quota = storage_mode == "platform"
        await self._check_quota(total_size, apply_quota=apply_quota)

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
            "created_at": datetime.utcnow().isoformat(),
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
        上传分片
        """
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
        session["uploaded_chunks"] = sorted(list(uploaded_chunks))

        uploaded_bytes = await self._calc_uploaded_bytes(upload_id, session["uploaded_chunks"])
        response = self._build_session_response(session, uploaded_bytes=uploaded_bytes)

        if progress_callback:
            await self._trigger_progress(progress_callback, response)

        await self._save_session(session)
        return response

    async def complete_chunk_upload(self, upload_id: str) -> dict[str, Any]:
        """
        完成分片上传并合并文件
        """
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
        apply_quota = storage_mode == "platform"
        await self._check_quota(size, apply_quota=apply_quota)
        storage_config = await self._resolve_storage_config(storage_mode)

        existing = await self.repo.get_by_hash(file_hash)
        if existing:
            await self._remove_temp_file(temp_path)
            await self._remove_session(upload_id)
            url = await self._get_existing_url(storage_config, existing)
            return {
                "attachment": existing,
                "url": url,
                "used_bytes": await self.repo.sum_size(),
            }

        storage_path = self._build_storage_path(session["filename"])
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
        )
        await self._remove_session(upload_id)
        used_bytes = await self.repo.sum_size()
        return {"attachment": attachment, "url": upload_result.url, "used_bytes": used_bytes}

    async def get_upload_status(self, upload_id: str) -> dict[str, Any]:
        """
        获取分片上传进度
        """
        session = await self._load_session(upload_id)
        uploaded_bytes = await self._calc_uploaded_bytes(
            upload_id, session.get("uploaded_chunks", [])
        )
        return self._build_session_response(session, uploaded_bytes=uploaded_bytes)

    async def abort_upload(self, upload_id: str) -> None:
        """
        取消上传并清理临时文件
        """
        await self._remove_session(upload_id)

    async def _ensure_upload_enabled(self) -> None:
        """
        检查租户上传功能开关
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

    async def _check_quota(self, additional_bytes: int, apply_quota: bool) -> None:
        """
        检查文件大小与存储配额
        """
        if not apply_quota:
            return
        tenant = await self._get_tenant()
        quota_service = QuotaService(self.db, tenant)

        size_check = quota_service.check_file_size(additional_bytes)
        if not size_check.allowed:
            raise BusinessException(
                message=_("file.file_too_large"),
                code=ErrorCode.INVALID_PARAMETER,
            )

        current_bytes = await self.repo.sum_size()
        storage_check = await quota_service.check_storage_quota(
            additional_bytes=additional_bytes,
            current_bytes=current_bytes,
        )
        if not storage_check.allowed:
            raise BusinessException(
                message=_("error.common.conflict"),
                code=ErrorCode.CONFLICT,
            )

    async def _get_tenant(self) -> Tenant:
        """
        获取租户信息（含套餐）
        """
        result = await self.db.execute(
            select(Tenant)
            .options(selectinload(Tenant.tenant_plan))
            .where(Tenant.id == self.tenant_id, Tenant.is_deleted == False)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise NotFoundException(message=_("tenant.not_found"))
        return tenant

    async def _save_to_temp(self, content: BinaryIO) -> tuple[str, int, str]:
        """
        将内容写入临时文件并计算哈希
        """
        def _write() -> tuple[str, int, str]:
            size = 0
            hasher = hashlib.md5()
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
        删除临时文件
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
        上传临时文件到存储驱动
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

    async def _get_existing_url(
        self,
        storage_config: StorageConfig,
        attachment: Attachment,
    ) -> str:
        """
        获取已存在附件的访问 URL
        """
        driver = storage_manager.get_driver(storage_config)
        visibility = StorageVisibility(attachment.visibility)
        return await driver.get_url(attachment.path, visibility=visibility)

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
    ) -> Attachment:
        """
        落库附件记录
        """
        extension = Path(filename).suffix.lstrip(".") if filename else None
        
        # 获取 base_url
        if storage_config:
            driver = storage_manager.get_driver(storage_config)
            base_url = driver.get_base_url()
        else:
            # 容错处理：如果没有 storage_config，使用空字符串
            base_url = ""
        
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
                "meta": metadata or {},
            }
        )
        return attachment

    async def _resolve_storage_context(self) -> tuple[str, StorageConfig, bool]:
        storage_mode = await self._get_storage_mode()
        storage_config = await self._resolve_storage_config(storage_mode)
        apply_quota = storage_mode == "platform"
        return storage_mode, storage_config, apply_quota

    async def _get_storage_mode(self) -> str:
        mode = await self._config_service.get_tenant_config(
            self.tenant_id,
            "tenant_storage_mode",
            default="platform",
        )
        return "custom" if str(mode) == "custom" else "platform"

    async def _resolve_storage_config(self, storage_mode: str) -> StorageConfig:
        """
        解析存储配置
        """
        if storage_mode == "custom":
            driver = await self._config_service.get_tenant_config(
                self.tenant_id, "tenant_storage_driver", default="s3"
            )
            if str(driver) == "local":
                raise BusinessException(
                    message=_("error.common.invalid_parameter"),
                    code=ErrorCode.INVALID_PARAMETER,
                )
            root_path = await self._config_service.get_tenant_config(
                self.tenant_id, "tenant_storage_root_path", default=""
            )
            if not root_path:
                raise BusinessException(
                    message=_("error.common.invalid_parameter"),
                    code=ErrorCode.INVALID_PARAMETER,
                )
            base_url = await self._config_service.get_tenant_config(
                self.tenant_id, "tenant_storage_base_url", default=None
            )
            options = await self._config_service.get_tenant_config(
                self.tenant_id, "tenant_storage_options", default={}
            )
        else:
            driver = await self._config_service.get_platform_config(
                "platform_storage_driver", default="local"
            )
            if str(driver) == "local":
                # 本地存储使用硬编码路径
                from app.storage import LOCAL_STORAGE_ROOT
                root_path = str(LOCAL_STORAGE_ROOT)
            else:
                root_path = await self._config_service.get_platform_config(
                    "platform_storage_root_path", default=""
                )
            base_url = await self._config_service.get_platform_config(
                "platform_storage_base_url", default=None
            )
            options = await self._config_service.get_platform_config(
                "platform_storage_options", default={}
            )
        return StorageConfig(
            driver=str(driver),
            root_path=str(root_path),
            base_url=base_url,
            options=options or {},
        )

    def _build_storage_path(self, filename: str) -> str:
        """
        构建存储路径
        """
        suffix = Path(filename).suffix if filename else ""
        date_path = datetime.utcnow().strftime("%Y/%m/%d")
        return f"{self.tenant_id}/{date_path}/{uuid.uuid4().hex}{suffix}"

    def _get_upload_root(self) -> Path:
        """
        获取上传临时根目录
        """
        return Path(tempfile.gettempdir()) / "novusai_uploads" / str(self.tenant_id)

    def _get_session_path(self, upload_id: str) -> Path:
        """
        获取上传会话路径
        """
        return self._get_upload_root() / upload_id

    def _get_session_file(self, upload_id: str) -> Path:
        """
        获取会话状态文件
        """
        return self._get_session_path(upload_id) / "session.json"

    def _get_chunk_path(self, upload_id: str, chunk_index: int) -> Path:
        """
        获取分片文件路径
        """
        return self._get_session_path(upload_id) / f"{chunk_index}.part"

    async def _save_session(self, session: dict[str, Any]) -> None:
        """
        保存会话状态
        """
        session_path = self._get_session_path(session["upload_id"])
        session_path.mkdir(parents=True, exist_ok=True)
        session_file = session_path / "session.json"

        def _write() -> None:
            session_file.write_text(json.dumps(session, ensure_ascii=False), encoding="utf-8")

        await anyio.to_thread.run_sync(_write)

    async def _load_session(self, upload_id: str) -> dict[str, Any]:
        """
        加载会话状态
        """
        session_file = self._get_session_file(upload_id)
        if not session_file.exists():
            raise BusinessException(
                message=_("error.common.not_found"),
                code=ErrorCode.NOT_FOUND,
            )

        def _read() -> dict[str, Any]:
            return json.loads(session_file.read_text(encoding="utf-8"))

        return await anyio.to_thread.run_sync(_read)

    async def _remove_session(self, upload_id: str) -> None:
        """
        删除会话及分片文件
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
        写入分片文件
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
        计算已上传字节数
        """
        def _sum() -> int:
            total = 0
            for chunk_index in chunks:
                chunk_path = self._get_chunk_path(upload_id, chunk_index)
                if chunk_path.exists():
                    total += chunk_path.stat().st_size
            return total

        return await anyio.to_thread.run_sync(_sum)

    async def _merge_chunks(self, upload_id: str, chunk_count: int) -> tuple[str, int, str]:
        """
        合并分片并计算哈希
        """
        def _merge() -> tuple[str, int, str]:
            size = 0
            hasher = hashlib.md5()
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
        计算分片数量
        """
        if chunk_size <= 0:
            return 0
        return (total_size + chunk_size - 1) // chunk_size

    def _build_session_response(self, session: dict[str, Any], uploaded_bytes: int) -> dict[str, Any]:
        """
        构建会话响应
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

    async def _trigger_progress(self, callback: ProgressCallback, payload: dict[str, Any]) -> None:
        """
        触发进度回调
        """
        result = callback(payload)
        if hasattr(result, "__await__"):
            await result

    # ========================================
    # 附件管理方法
    # ========================================

    async def soft_delete(self, attachment_id: int) -> bool:
        """
        软删除附件
        
        Args:
            attachment_id: 附件 ID
        
        Returns:
            是否删除成功
        """
        attachment = await self.repo.get_by_id(attachment_id)
        if not attachment:
            raise NotFoundException(message=_("error.common.not_found"))
        return await self.repo.delete(attachment_id, soft=True)

    async def get_storage_stats(self) -> dict[str, Any]:
        """
        获取租户存储统计
        
        Returns:
            存储统计信息
        """
        total_size = await self.repo.sum_size()
        total_count = await self.repo.count()
        return {
            "total_size": total_size,
            "total_count": total_count,
        }


__all__ = ["AttachmentService"]
