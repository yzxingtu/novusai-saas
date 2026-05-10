"""中文: AI 测试模块分类标记。

EN: AI test module classification marker.

Test type: structural / behavioral
Scope: Existing AI tests in this module; no real-dialogue smoke acceptance is claimed.
"""

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
async def test_resolve_image_url_for_llm_accepts_attachment_id_hint_without_url() -> (
    None
):
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
