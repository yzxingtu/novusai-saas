from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.testclient import TestClient

from app.api.public import attachments as attachments_api
from app.core.deps import get_db


def _build_test_app(db: AsyncMock) -> FastAPI:
    app = FastAPI()
    app.include_router(attachments_api.router, prefix="/api/public")

    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return app


def test_public_image_endpoint_redirects_to_processed_url(
    monkeypatch,
) -> None:
    from app.configs.service import ConfigService
    from app.services.common import ImageProcessService
    from app.services.tenant.attachment_download_service import (
        AttachmentDownloadService,
    )

    attachment_record = SimpleNamespace(
        id=26,
        tenant_id=23,
        driver="s3",
        path="images/demo.png",
    )
    params = SimpleNamespace(is_empty=lambda: False)

    async def fake_get_platform_config(self, key: str, default=None):
        assert key == "platform_image_process_rate_limit"
        return default

    async def fake_get_attachment(self, attachment_id: int):
        assert attachment_id == 26
        return attachment_record

    async def fake_validate_access(self, attachment_arg, token):
        assert attachment_arg is attachment_record
        assert token is None

    async def fake_is_enabled(self):
        return True

    async def fake_parse_params(self, **kwargs):
        assert kwargs["width"] == 320
        return params

    async def fake_get_processed_image_response(self, attachment_arg, params_arg):
        assert attachment_arg is attachment_record
        assert params_arg is params
        return "https://cdn.example.com/processed/demo.webp"

    monkeypatch.setattr(
        ConfigService,
        "get_platform_config",
        fake_get_platform_config,
    )
    monkeypatch.setattr(
        AttachmentDownloadService,
        "get_attachment",
        fake_get_attachment,
    )
    monkeypatch.setattr(
        AttachmentDownloadService,
        "validate_access",
        fake_validate_access,
    )
    monkeypatch.setattr(ImageProcessService, "is_enabled", fake_is_enabled)
    monkeypatch.setattr(ImageProcessService, "parse_params", fake_parse_params)
    monkeypatch.setattr(
        ImageProcessService,
        "get_processed_image_response",
        fake_get_processed_image_response,
    )

    attachments_api._image_rate_buckets.clear()
    attachments_api._last_eviction = 0.0

    app = _build_test_app(AsyncMock())

    with TestClient(app) as client:
        response = client.get(
            "/api/public/attachments/26/image?w=320",
            follow_redirects=False,
        )

    assert response.status_code == 307
    assert response.headers["location"] == "https://cdn.example.com/processed/demo.webp"


def test_public_access_endpoint_returns_404_when_cloud_redirect_falls_back_to_api(
    monkeypatch,
) -> None:
    from app.services.tenant.attachment_download_service import (
        AttachmentDownloadService,
    )

    attachment_record = SimpleNamespace(
        id=51,
        tenant_id=7,
        driver="s3",
        path="private/demo.png",
    )

    async def fake_get_attachment(self, attachment_id: int):
        assert attachment_id == 51
        return attachment_record

    async def fake_validate_access(self, attachment_arg, token):
        assert attachment_arg is attachment_record
        assert token is None

    async def fake_get_redirect_url(self, attachment_arg, expires: int, preview: bool):
        assert attachment_arg is attachment_record
        assert expires == 3600
        assert preview is False
        return "/api/public/attachments/51/access"

    monkeypatch.setattr(
        AttachmentDownloadService,
        "get_attachment",
        fake_get_attachment,
    )
    monkeypatch.setattr(
        AttachmentDownloadService,
        "validate_access",
        fake_validate_access,
    )
    monkeypatch.setattr(
        AttachmentDownloadService,
        "get_redirect_url",
        fake_get_redirect_url,
    )

    app = _build_test_app(AsyncMock())

    with TestClient(app) as client:
        response = client.get(
            "/api/public/attachments/51/access",
            follow_redirects=False,
        )

    assert response.status_code == 404
    payload = response.json()
    assert payload["code"] == 4040
    assert payload["message"] == "File storage config unavailable"


def test_public_access_endpoint_streams_local_preview_and_records_download(
    monkeypatch,
) -> None:
    from app.services.tenant.attachment_download_service import (
        AttachmentDownloadService,
    )

    attachment_record = SimpleNamespace(
        id=19,
        tenant_id=7,
        driver="local",
        path="uploads/demo.txt",
    )
    record_download = AsyncMock()
    get_download_response = AsyncMock(
        return_value=Response(
            content=b"demo",
            media_type="text/plain",
            headers={"Content-Disposition": "inline"},
        )
    )

    async def fake_get_attachment(self, attachment_id: int):
        assert attachment_id == 19
        return attachment_record

    async def fake_validate_access(self, attachment_arg, token):
        assert attachment_arg is attachment_record
        assert token is None

    monkeypatch.setattr(
        AttachmentDownloadService,
        "get_attachment",
        fake_get_attachment,
    )
    monkeypatch.setattr(
        AttachmentDownloadService,
        "validate_access",
        fake_validate_access,
    )
    monkeypatch.setattr(
        AttachmentDownloadService,
        "record_download",
        record_download,
    )
    monkeypatch.setattr(
        AttachmentDownloadService,
        "get_download_response",
        get_download_response,
    )

    app = _build_test_app(AsyncMock())

    with TestClient(app) as client:
        response = client.get(
            "/api/public/attachments/19/access?preview=true",
            follow_redirects=False,
        )

    assert response.status_code == 200
    assert response.headers["content-disposition"] == "inline"
    record_download.assert_awaited_once_with(attachment_record)
    get_download_response.assert_awaited_once_with(attachment_record, preview=True)
