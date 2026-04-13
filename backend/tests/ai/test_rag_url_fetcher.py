from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.ai.tools.security import SSRFBlockedError
from app.exceptions import BusinessException


class _FakeStreamResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        chunks: list[bytes] | None = None,
        encoding: str = "utf-8",
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = list(chunks or [])
        self.encoding = encoding

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class _FakeAsyncClient:
    def __init__(self, responses: list[_FakeStreamResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, method: str, url: str):
        self.calls.append((method, url))
        return self._responses.pop(0)


@pytest.mark.asyncio
async def test_fetch_public_url_text_blocks_ssrf_urls() -> None:
    from app.ai.rag.url_fetcher import fetch_public_url_text

    with patch(
        "app.ai.rag.url_fetcher.UrlValidator.validate",
        new=AsyncMock(side_effect=SSRFBlockedError("blocked")),
    ):
        with pytest.raises(BusinessException):
            await fetch_public_url_text("http://169.254.169.254/latest/meta-data")


@pytest.mark.asyncio
async def test_fetch_public_url_text_rejects_large_content_length() -> None:
    from app.ai.rag.url_fetcher import fetch_public_url_text

    fake_client = _FakeAsyncClient(
        [
            _FakeStreamResponse(
                headers={
                    "content-type": "text/html; charset=utf-8",
                    "content-length": str(3 * 1024 * 1024),
                },
                chunks=[b"<html></html>"],
            )
        ]
    )

    with patch(
        "app.ai.rag.url_fetcher.UrlValidator.validate",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.ai.rag.url_fetcher.httpx.AsyncClient",
        new=lambda **_kwargs: fake_client,
    ):
        with pytest.raises(BusinessException):
            await fetch_public_url_text("https://example.com/page")


@pytest.mark.asyncio
async def test_fetch_public_url_text_rejects_non_text_content_type() -> None:
    from app.ai.rag.url_fetcher import fetch_public_url_text

    fake_client = _FakeAsyncClient(
        [
            _FakeStreamResponse(
                headers={"content-type": "application/octet-stream"},
                chunks=[b"not html"],
            )
        ]
    )

    with patch(
        "app.ai.rag.url_fetcher.UrlValidator.validate",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.ai.rag.url_fetcher.httpx.AsyncClient",
        new=lambda **_kwargs: fake_client,
    ):
        with pytest.raises(BusinessException):
            await fetch_public_url_text("https://example.com/file.bin")


@pytest.mark.asyncio
async def test_fetch_public_url_text_follows_safe_redirects() -> None:
    from app.ai.rag.url_fetcher import fetch_public_url_text

    fake_client = _FakeAsyncClient(
        [
            _FakeStreamResponse(
                status_code=302,
                headers={"location": "/landing"},
            ),
            _FakeStreamResponse(
                headers={"content-type": "text/html; charset=utf-8"},
                chunks=[b"<html><body>Hello</body></html>"],
            ),
        ]
    )

    with patch(
        "app.ai.rag.url_fetcher.UrlValidator.validate",
        new=AsyncMock(return_value=None),
    ) as validate, patch(
        "app.ai.rag.url_fetcher.httpx.AsyncClient",
        new=lambda **_kwargs: fake_client,
    ):
        text = await fetch_public_url_text("https://example.com")

    assert "Hello" in text
    assert fake_client.calls == [
        ("GET", "https://example.com"),
        ("GET", "https://example.com/landing"),
    ]
    assert validate.await_count == 2
