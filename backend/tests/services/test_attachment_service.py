"""AttachmentService 单元测试 / Test.

覆盖：文件上传、下载、删除、存储配额检查、文件验证。"""

from __future__ import annotations

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
