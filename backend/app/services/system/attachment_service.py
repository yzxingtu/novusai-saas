"""
平台端附件服务

提供跨租户的附件管理能力（平台管理员专用）
"""

import hashlib
import json
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO

import anyio
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import ConfigService
from app.core.base_service import GlobalService
from app.core.i18n import _
from app.enums import ErrorCode
from app.enums.attachment import AttachmentSource, AttachmentStatus, AttachmentVisibility
from app.exceptions import BusinessException, NotFoundException
from app.models.tenant.attachment import Attachment
from app.repositories.system.attachment_repository import AdminAttachmentRepository
from app.services.common.file_validator import FileValidator, validate_result_or_raise
from app.storage import StorageConfig, StorageVisibility, storage_manager


class AdminAttachmentService(GlobalService[Attachment, AdminAttachmentRepository]):
    """
    平台端附件服务
    
    提供跨租户的附件管理能力
    """
    
    model = Attachment
    repository_class = AdminAttachmentRepository

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self._config_service = ConfigService(db)
        self._file_validator = FileValidator(db)

    # ========== 上传方法 ==========

    async def upload_file(
        self,
        tenant_id: int,
        content: BinaryIO,
        filename: str,
        file_size: int | None = None,
        mime_type: str | None = None,
        visibility: AttachmentVisibility = AttachmentVisibility.PRIVATE,
        source: AttachmentSource = AttachmentSource.PLATFORM_ADMIN,
        uploader_id: int | None = None,
        business_type: str | None = None,
        business_id: int | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """
        平台端上传文件
        
        不受租户配额限制，使用平台存储配置
        
        Args:
            tenant_id: 目标租户 ID
            content: 文件内容
            filename: 文件名
            file_size: 文件大小
            mime_type: MIME 类型
            visibility: 可见性
            source: 上传来源
            uploader_id: 上传者 ID
            business_type: 业务类型
            business_id: 业务 ID
            metadata: 元数据
        
        Returns:
            上传结果
        """
        # 验证文件类型
        validation_result = await self._file_validator.validate_for_platform(
            filename, file_size
        )
        validate_result_or_raise(validation_result)

        storage_config = await self._resolve_platform_storage_config()
        temp_path, size, file_hash = await self._save_to_temp(content)
        actual_size = file_size or size

        # 检查同租户是否已存在相同哈希的文件
        existing = await self.repo.get_by_hash(file_hash, tenant_id=tenant_id)
        if existing:
            await self._remove_temp_file(temp_path)
            driver = storage_manager.get_driver(storage_config)
            url = await driver.get_url(
                existing.path,
                visibility=StorageVisibility(existing.visibility),
            )
            return {
                "attachment": existing,
                "url": url,
            }

        storage_path = self._build_storage_path(tenant_id, filename)
        upload_result = await self._upload_to_storage(
            storage_config=storage_config,
            storage_path=storage_path,
            temp_path=temp_path,
            mime_type=mime_type,
            visibility=visibility,
            metadata=metadata,
        )
        attachment = await self._create_attachment(
            tenant_id=tenant_id,
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
        return {"attachment": attachment, "url": upload_result.url}

    async def start_chunk_upload(
        self,
        tenant_id: int,
        filename: str,
        total_size: int,
        chunk_size: int,
        mime_type: str | None = None,
        visibility: AttachmentVisibility = AttachmentVisibility.PRIVATE,
        source: AttachmentSource = AttachmentSource.PLATFORM_ADMIN,
        uploader_id: int | None = None,
        business_type: str | None = None,
        business_id: int | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """
        初始化分片上传会话
        """
        # 验证文件类型
        validation_result = await self._file_validator.validate_for_platform(
            filename, total_size
        )
        validate_result_or_raise(validation_result)

        if total_size <= 0 or chunk_size <= 0:
            raise BusinessException(
                message=_("error.common.invalid_parameter"),
                code=ErrorCode.INVALID_PARAMETER,
            )
        upload_id = uuid.uuid4().hex
        session = {
            "upload_id": upload_id,
            "tenant_id": tenant_id,
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
        await self._save_session(session)
        return self._build_session_response(session, uploaded_bytes=uploaded_bytes)

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
        storage_config = await self._resolve_platform_storage_config()
        tenant_id = int(session["tenant_id"])

        # 检查是否已存在
        existing = await self.repo.get_by_hash(file_hash, tenant_id=tenant_id)
        if existing:
            await self._remove_temp_file(temp_path)
            await self._remove_session(upload_id)
            driver = storage_manager.get_driver(storage_config)
            url = await driver.get_url(
                existing.path,
                visibility=StorageVisibility(existing.visibility),
            )
            return {
                "attachment": existing,
                "url": url,
            }

        storage_path = self._build_storage_path(tenant_id, session["filename"])
        upload_result = await self._upload_to_storage(
            storage_config=storage_config,
            storage_path=storage_path,
            temp_path=temp_path,
            mime_type=session.get("mime_type"),
            visibility=AttachmentVisibility(session["visibility"]),
            metadata=session.get("metadata"),
        )
        attachment = await self._create_attachment(
            tenant_id=tenant_id,
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
        return {"attachment": attachment, "url": upload_result.url}

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

    # ========== 私有方法 ==========

    async def _resolve_platform_storage_config(self) -> StorageConfig:
        """
        获取平台存储配置
        """
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

    async def _create_attachment(
        self,
        tenant_id: int,
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
            base_url = ""
        
        attachment = await self.repo.create(
            {
                "tenant_id": tenant_id,
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

    def _build_storage_path(self, tenant_id: int, filename: str) -> str:
        """
        构建存储路径
        
        - tenant_id=0: 平台附件，路径为 platform/{date}/{uuid}.ext
        - tenant_id>0: 租户附件，路径为 {tenant_id}/{date}/{uuid}.ext
        """
        suffix = Path(filename).suffix if filename else ""
        date_path = datetime.utcnow().strftime("%Y/%m/%d")
        prefix = "platform" if tenant_id == 0 else str(tenant_id)
        return f"{prefix}/{date_path}/{uuid.uuid4().hex}{suffix}"

    def _get_upload_root(self) -> Path:
        """
        获取上传临时根目录
        """
        return Path(tempfile.gettempdir()) / "novusai_uploads" / "admin"

    def _get_session_path(self, upload_id: str) -> Path:
        return self._get_upload_root() / upload_id

    def _get_session_file(self, upload_id: str) -> Path:
        return self._get_session_path(upload_id) / "session.json"

    def _get_chunk_path(self, upload_id: str, chunk_index: int) -> Path:
        return self._get_session_path(upload_id) / f"{chunk_index}.part"

    async def _save_session(self, session: dict[str, Any]) -> None:
        session_path = self._get_session_path(session["upload_id"])
        session_path.mkdir(parents=True, exist_ok=True)
        session_file = session_path / "session.json"
        def _write() -> None:
            session_file.write_text(json.dumps(session, ensure_ascii=False), encoding="utf-8")
        await anyio.to_thread.run_sync(_write)

    async def _load_session(self, upload_id: str) -> dict[str, Any]:
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
        session_path = self._get_session_path(upload_id)
        def _remove() -> None:
            if session_path.exists():
                for item in session_path.iterdir():
                    item.unlink(missing_ok=True)
                session_path.rmdir()
        await anyio.to_thread.run_sync(_remove)

    async def _write_chunk(self, chunk_path: Path, content: BinaryIO) -> None:
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
        def _sum() -> int:
            total = 0
            for chunk_index in chunks:
                chunk_path = self._get_chunk_path(upload_id, chunk_index)
                if chunk_path.exists():
                    total += chunk_path.stat().st_size
            return total
        return await anyio.to_thread.run_sync(_sum)

    async def _merge_chunks(self, upload_id: str, chunk_count: int) -> tuple[str, int, str]:
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
        if chunk_size <= 0:
            return 0
        return (total_size + chunk_size - 1) // chunk_size

    def _build_session_response(self, session: dict[str, Any], uploaded_bytes: int) -> dict[str, Any]:
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

    # ========== 管理方法 ==========

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

    async def get_storage_stats(self, tenant_id: int | None = None) -> dict[str, Any]:
        """
        获取存储统计
        
        Args:
            tenant_id: 可选的租户 ID，不传则统计所有租户
        
        Returns:
            存储统计信息
        """
        return await self.repo.get_storage_stats(tenant_id)

    async def get_storage_stats_by_tenant(self) -> list[dict[str, Any]]:
        """
        获取按租户分组的存储统计
        
        Returns:
            各租户存储统计列表
        """
        return await self.repo.get_storage_stats_by_tenant()


__all__ = ["AdminAttachmentService"]
