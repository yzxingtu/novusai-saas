"""
Public URL fetch support for knowledge-base ingestion.
"""

from __future__ import annotations

from urllib.parse import urljoin

import httpx

from app.ai.tools.security import SSRFBlockedError, UrlValidator
from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException

logger = LogManager.get_logger("ai.rag.url_fetcher")

_MAX_FETCH_BYTES = 2 * 1024 * 1024
_MAX_REDIRECTS = 3
_ALLOWED_CONTENT_TYPE_MARKERS = (
    "text/html",
    "application/xhtml+xml",
    "text/plain",
)


def _ensure_supported_content_type(content_type: str) -> None:
    normalized = str(content_type or "").lower()
    if not normalized:
        return
    if any(marker in normalized for marker in _ALLOWED_CONTENT_TYPE_MARKERS):
        return
    raise BusinessException(message=_("knowledge_base.document.error.parse_failed"))


async def fetch_public_url_text(
    url: str,
    *,
    timeout: float = 30.0,
    max_bytes: int = _MAX_FETCH_BYTES,
) -> str:
    """Fetch a public URL with SSRF, redirect, size, and content-type guards."""
    try:
        await UrlValidator.validate(url)
    except SSRFBlockedError as exc:
        logger.warning("RAG URL blocked by SSRF guard: url={} err={}", url, str(exc))
        raise BusinessException(message=_("knowledge_base.document.error.parse_failed")) from exc

    current_url = url
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for _redirect_index in range(_MAX_REDIRECTS + 1):
            async with client.stream("GET", current_url) as response:
                status_code = int(response.status_code)
                if 300 <= status_code < 400 and response.headers.get("location"):
                    redirected_url = urljoin(current_url, response.headers["location"])
                    try:
                        await UrlValidator.validate(redirected_url)
                    except SSRFBlockedError as exc:
                        logger.warning(
                            "RAG redirect blocked by SSRF guard: from={} to={} err={}",
                            current_url,
                            redirected_url,
                            str(exc),
                        )
                        raise BusinessException(
                            message=_("knowledge_base.document.error.parse_failed")
                        ) from exc
                    current_url = redirected_url
                    continue

                response.raise_for_status()

                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        if int(content_length) > max_bytes:
                            raise BusinessException(
                                message=_("knowledge_base.document.error.parse_failed")
                            )
                    except ValueError:
                        logger.warning(
                            "Ignore invalid content-length during URL ingestion: url={} value={}",
                            current_url,
                            content_length,
                        )

                _ensure_supported_content_type(response.headers.get("content-type", ""))

                collected = bytearray()
                async for chunk in response.aiter_bytes():
                    collected.extend(chunk)
                    if len(collected) > max_bytes:
                        raise BusinessException(
                            message=_("knowledge_base.document.error.parse_failed")
                        )

                encoding = response.encoding or "utf-8"
                return collected.decode(encoding, errors="replace")

    raise BusinessException(message=_("knowledge_base.document.error.parse_failed"))


__all__ = ["fetch_public_url_text"]
