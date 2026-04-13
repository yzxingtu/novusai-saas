"""
Public HTML transport helpers. / 公共 HTML 传输支持。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class PublicHtmlTransportError(RuntimeError):
    """Transport error while fetching public HTML."""


class PublicHtmlTransportTimeout(PublicHtmlTransportError):
    """Timeout while fetching public HTML."""


@dataclass(frozen=True)
class PublicHtmlResponse:
    status_code: int
    text: str


_DEFAULT_WEB_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "text/plain;q=0.8,*/*;q=0.7"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}


async def fetch_public_html(
    url: str,
    *,
    params: dict[str, Any],
    timeout_seconds: int,
) -> PublicHtmlResponse:
    import httpx

    try:
        timeout = httpx.Timeout(float(timeout_seconds), connect=min(10.0, float(timeout_seconds)))
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=_DEFAULT_WEB_HEADERS,
        ) as client:
            resp = await client.get(url, params=params)
    except httpx.TimeoutException as exc:
        raise PublicHtmlTransportTimeout("timeout") from exc
    except Exception as exc:  # noqa: BLE001
        raise PublicHtmlTransportError(str(exc)) from exc
    return PublicHtmlResponse(status_code=resp.status_code, text=resp.text)


__all__ = [
    "PublicHtmlResponse",
    "PublicHtmlTransportError",
    "PublicHtmlTransportTimeout",
    "fetch_public_html",
]
