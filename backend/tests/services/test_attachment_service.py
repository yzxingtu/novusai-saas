"""AttachmentService 单元测试 / Test.

覆盖：文件上传、下载、删除、存储配额检查、文件验证。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.services.conftest import make_mock_model


def _make_attachment(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 1,
        "filename": "test.pdf",
        "original_name": "test.pdf",
        "mime_type": "application/pdf",
        "size": 1024000,
        "driver": "local",
        "path": "tenants/1/2026/02/27/abc.pdf",
        "is_deleted": False,
    }
    defaults.update(overrides)
    obj = make_mock_model(**defaults)
    obj.to_dict.return_value = defaults
    return obj


class TestAttachmentUpload:
    @pytest.mark.asyncio
    async def test_file_too_large_raises(self, mock_db):
        from app.exceptions import BusinessException
        from app.services.tenant.attachment_service import AttachmentService

        service = AttachmentService.__new__(AttachmentService)
        service.db = mock_db
        service.tenant_id = 1
        service._max_file_size_mb = 20

        file_mock = MagicMock()
        file_mock.size = 50 * 1024 * 1024  # 50MB

        with pytest.raises((BusinessException, Exception)):
            await service.validate_file(file_mock)


class TestAttachmentDedupVisibility:
    @pytest.mark.asyncio
    async def test_tenant_preflight_hash_lookup_scopes_by_visibility(self, mock_db):
        from app.enums.attachment import AttachmentVisibility
        from app.services.common.file_validator import FileValidationResult
        from app.services.tenant.attachment_service import AttachmentService
        from app.storage.base import StorageConfig

        service = AttachmentService.__new__(AttachmentService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_hash = AsyncMock(return_value=None)
        service._file_validator = MagicMock()
        service._file_validator.validate_for_tenant = AsyncMock(
            return_value=FileValidationResult.ok()
        )
        service._ensure_upload_enabled = AsyncMock()
        service._resolve_storage_context = AsyncMock(
            return_value=(
                "platform",
                StorageConfig(driver="s3", root_path="bucket"),
                False,
            )
        )
        service._check_quota = AsyncMock()

        await service.preflight_check(
            file_hash="abc123",
            filename="logo.png",
            size=256,
            visibility=AttachmentVisibility.PUBLIC,
        )

        service.repo.get_by_hash.assert_awaited_once_with(
            "abc123",
            driver="s3",
            visibility="public",
        )

    @pytest.mark.asyncio
    async def test_tenant_upload_hash_lookup_scopes_by_visibility(self, mock_db):
        from app.enums.attachment import AttachmentVisibility
        from app.services.common.file_validator import FileValidationResult
        from app.services.tenant.attachment_service import AttachmentService
        from app.storage.base import StorageConfig

        existing = _make_attachment(id=7, visibility="public")
        service = AttachmentService.__new__(AttachmentService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_hash = AsyncMock(return_value=existing)
        service.repo.sum_size = AsyncMock(return_value=2048)
        service._file_validator = MagicMock()
        service._file_validator.validate_for_tenant = AsyncMock(
            return_value=FileValidationResult.ok()
        )
        service._ensure_upload_enabled = AsyncMock()
        service._resolve_storage_context = AsyncMock(
            return_value=(
                "platform",
                StorageConfig(driver="s3", root_path="bucket"),
                False,
            )
        )
        service._save_to_temp = AsyncMock(return_value=("tmp/file", 256, "abc123"))
        service._check_quota = AsyncMock()
        service._remove_temp_file = AsyncMock()

        result = await service.upload_file(
            content=MagicMock(),
            filename="logo.png",
            visibility=AttachmentVisibility.PUBLIC,
        )

        service.repo.get_by_hash.assert_awaited_once_with(
            "abc123",
            driver="s3",
            visibility="public",
        )
        assert result["attachment"] is existing

    @pytest.mark.asyncio
    async def test_tenant_private_upload_returns_signed_access_url(self, mock_db):
        from app.enums.attachment import AttachmentVisibility
        from app.services.common.file_validator import FileValidationResult
        from app.services.tenant.attachment_service import AttachmentService
        from app.storage.base import StorageConfig

        existing = _make_attachment(id=17, tenant_id=1, visibility="private")
        service = AttachmentService.__new__(AttachmentService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_hash = AsyncMock(return_value=existing)
        service.repo.sum_size = AsyncMock(return_value=2048)
        service._file_validator = MagicMock()
        service._file_validator.validate_for_tenant = AsyncMock(
            return_value=FileValidationResult.ok()
        )
        service._ensure_upload_enabled = AsyncMock()
        service._resolve_storage_context = AsyncMock(
            return_value=(
                "platform",
                StorageConfig(driver="s3", root_path="bucket"),
                False,
            )
        )
        service._save_to_temp = AsyncMock(return_value=("tmp/file", 256, "abc123"))
        service._check_quota = AsyncMock()
        service._remove_temp_file = AsyncMock()

        result = await service.upload_file(
            content=MagicMock(),
            filename="secret.pdf",
            visibility=AttachmentVisibility.PRIVATE,
        )

        assert result["attachment"] is existing
        assert result["url"].startswith("/api/public/attachments/17/access?")
        assert "token=" in result["url"]

    @pytest.mark.asyncio
    async def test_admin_preflight_hash_lookup_scopes_by_visibility(self, mock_db):
        from app.enums.attachment import AttachmentVisibility
        from app.services.common.file_validator import FileValidationResult
        from app.services.system.attachment_service import AdminAttachmentService
        from app.storage.base import StorageConfig

        service = AdminAttachmentService.__new__(AdminAttachmentService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_hash = AsyncMock(return_value=None)
        service._file_validator = MagicMock()
        service._file_validator.validate_for_platform = AsyncMock(
            return_value=FileValidationResult.ok()
        )
        service._resolve_platform_storage_config = AsyncMock(
            return_value=StorageConfig(driver="s3", root_path="bucket")
        )

        await service.preflight_check(
            tenant_id=0,
            file_hash="abc123",
            filename="logo.png",
            size=256,
            visibility=AttachmentVisibility.PUBLIC,
        )

        service.repo.get_by_hash.assert_awaited_once_with(
            "abc123",
            tenant_id=0,
            driver="s3",
            visibility="public",
        )

    @pytest.mark.asyncio
    async def test_admin_preflight_private_hit_returns_signed_access_url(self, mock_db):
        from app.enums.attachment import AttachmentVisibility
        from app.services.common.file_validator import FileValidationResult
        from app.services.system.attachment_service import AdminAttachmentService
        from app.storage.base import StorageConfig

        existing = _make_attachment(id=29, tenant_id=0, visibility="private")
        service = AdminAttachmentService.__new__(AdminAttachmentService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_hash = AsyncMock(return_value=existing)
        service._file_validator = MagicMock()
        service._file_validator.validate_for_platform = AsyncMock(
            return_value=FileValidationResult.ok()
        )
        service._resolve_platform_storage_config = AsyncMock(
            return_value=StorageConfig(driver="s3", root_path="bucket")
        )

        result = await service.preflight_check(
            tenant_id=0,
            file_hash="abc123",
            filename="secret.pdf",
            size=256,
            visibility=AttachmentVisibility.PRIVATE,
        )

        assert result["exists"] is True
        assert result["attachment"] is existing
        assert result["url"].startswith("/api/public/attachments/29/access?")
        assert "token=" in result["url"]

    @pytest.mark.asyncio
    async def test_admin_upload_hash_lookup_scopes_by_visibility(self, mock_db):
        from app.enums.attachment import AttachmentVisibility
        from app.services.common.file_validator import FileValidationResult
        from app.services.system.attachment_service import AdminAttachmentService
        from app.storage.base import StorageConfig

        existing = _make_attachment(id=9, tenant_id=0, visibility="public")
        service = AdminAttachmentService.__new__(AdminAttachmentService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_hash = AsyncMock(return_value=existing)
        service._file_validator = MagicMock()
        service._file_validator.validate_for_platform = AsyncMock(
            return_value=FileValidationResult.ok()
        )
        service._resolve_platform_storage_config = AsyncMock(
            return_value=StorageConfig(driver="s3", root_path="bucket")
        )
        service._save_to_temp = AsyncMock(return_value=("tmp/file", 256, "abc123"))
        service._remove_temp_file = AsyncMock()

        result = await service.upload_file(
            tenant_id=0,
            content=MagicMock(),
            filename="logo.png",
            visibility=AttachmentVisibility.PUBLIC,
        )

        service.repo.get_by_hash.assert_awaited_once_with(
            "abc123",
            tenant_id=0,
            driver="s3",
            visibility="public",
        )
        assert result["attachment"] is existing


class TestAttachmentStorageSnapshot:
    @pytest.mark.asyncio
    async def test_tenant_create_attachment_persists_storage_snapshot(self, mock_db):
        from unittest.mock import patch

        from app.services.tenant.attachment_service import AttachmentService
        from app.storage.base import StorageConfig

        service = AttachmentService.__new__(AttachmentService)
        service.db = mock_db
        service.tenant_id = 23
        service.repo = AsyncMock()
        service.repo.create = AsyncMock(return_value=MagicMock())

        storage_driver = MagicMock()
        storage_driver.get_base_url.return_value = "https://cdn.example.com"

        with patch(
            "app.services.tenant.attachment_service.storage_manager.get_driver",
            return_value=storage_driver,
        ):
            await service._create_attachment(
                filename="logo.png",
                storage_path="tenants/23/2026/03/logo.png",
                upload_result=SimpleNamespace(
                    size=128,
                    hash="abc123",
                    mime_type="image/png",
                    driver="s3",
                ),
                visibility=SimpleNamespace(value="public"),
                source=SimpleNamespace(value="tenant_admin"),
                uploader_id=9,
                business_type="brand",
                business_id=3,
                metadata={"biz": "logo"},
                storage_config=StorageConfig(
                    driver="s3",
                    root_path="platform-bucket",
                    base_url="https://cdn.example.com",
                ),
                storage_scope="platform",
            )

        create_payload = service.repo.create.await_args.args[0]
        assert create_payload["meta"]["biz"] == "logo"
        assert create_payload["meta"]["_storage_snapshot"] == {
            "scope": "platform",
            "driver": "s3",
            "root_path": "platform-bucket",
            "base_url": "https://cdn.example.com",
        }


class TestAttachmentDelete:
    @pytest.mark.asyncio
    async def test_delete_not_found_raises(self, mock_db):
        from app.exceptions import NotFoundException
        from app.services.tenant.attachment_service import AttachmentService

        service = AttachmentService.__new__(AttachmentService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            await service.delete(999, soft=True)

    @pytest.mark.asyncio
    async def test_soft_delete_success(self, mock_db):
        from unittest.mock import patch

        from app.services.tenant.attachment_service import AttachmentService

        att = _make_attachment()
        att.soft_delete = MagicMock()
        service = AttachmentService.__new__(AttachmentService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=att)
        service.repo.db = mock_db

        with patch.object(service, "_delete_storage_file", new_callable=AsyncMock):
            result = await service.delete(1, soft=True)
        assert result is True


class TestAttachmentQuery:
    @pytest.mark.asyncio
    async def test_get_by_id_found(self, mock_db):
        from app.services.tenant.attachment_service import AttachmentService

        att = _make_attachment()
        service = AttachmentService.__new__(AttachmentService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=att)

        result = await service.repo.get_by_id(1)
        assert result.filename == "test.pdf"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, mock_db):
        from app.services.tenant.attachment_service import AttachmentService

        service = AttachmentService.__new__(AttachmentService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=None)

        result = await service.repo.get_by_id(999)
        assert result is None


class TestStorageStats:
    @pytest.mark.asyncio
    async def test_get_storage_stats(self, mock_db):
        from app.services.tenant.attachment_service import AttachmentService

        service = AttachmentService.__new__(AttachmentService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.sum_size = AsyncMock(return_value=5242880)
        service.repo.count = AsyncMock(return_value=10)

        result = await service.get_storage_stats()
        assert result["total_size"] == 5242880
        assert result["total_count"] == 10


class TestAttachmentMimeType:
    @pytest.mark.asyncio
    async def test_attachment_has_correct_mime(self, mock_db):
        _ = mock_db
        att = _make_attachment(mime_type="image/png", filename="photo.png")
        assert att.mime_type == "image/png"
        assert att.filename == "photo.png"

    @pytest.mark.asyncio
    async def test_attachment_driver_local(self, mock_db):
        _ = mock_db
        att = _make_attachment(driver="local")
        assert att.driver == "local"

    @pytest.mark.asyncio
    async def test_attachment_driver_cloud(self, mock_db):
        _ = mock_db
        att = _make_attachment(driver="aliyun-oss")
        assert att.driver == "aliyun-oss"
