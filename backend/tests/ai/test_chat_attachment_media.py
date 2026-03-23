from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.utils import chat_attachment_media as media


def test_attachment_id_from_image_url_parses_preview_path() -> None:
    aid, token = media._attachment_id_from_url(
        "/api/public/attachments/12/image?token=jwt-token&exp=1&sign=abc",
    )

    assert aid == 12
    assert token == "jwt-token"


@pytest.mark.asyncio
async def test_resolve_image_url_for_llm_reads_db_for_relative_image_path() -> None:
    db = MagicMock()

    with (
        patch.object(
            media,
            "_read_attachment_bytes_via_db",
            new=AsyncMock(return_value=(b"png-bytes", "image/png")),
        ) as read_mock,
        patch.object(
            media,
            "_fetch_url_bytes",
            new=AsyncMock(),
        ) as fetch_mock,
    ):
        result = await media.resolve_image_url_for_llm(
            "/api/public/attachments/7/image?exp=1&sign=abc",
            "image/png",
            db=db,
            tenant_id=3,
        )

    assert result == "data:image/png;base64,cG5nLWJ5dGVz"
    assert read_mock.await_args.args[:4] == (db, 3, 7, None)
    fetch_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_image_url_for_llm_accepts_attachment_id_hint_without_url() -> None:
    db = MagicMock()

    with patch.object(
        media,
        "_read_attachment_bytes_via_db",
        new=AsyncMock(return_value=(b"jpg-bytes", "image/jpeg")),
    ) as read_mock:
        result = await media.resolve_image_url_for_llm(
            "",
            "image/jpeg",
            db=db,
            tenant_id=9,
            attachment_id="18",
        )

    assert result == "data:image/jpeg;base64,anBnLWJ5dGVz"
    assert read_mock.await_args.args[:4] == (db, 9, 18, None)
