"""
GitHub source allowlist helpers / GitHub 来源白名单辅助工具
"""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

import httpx

_ALLOWED_GITHUB_HOSTS = frozenset(
    {
        "github.com",
        "raw.githubusercontent.com",
        "objects.githubusercontent.com",
        "api.github.com",
        "codeload.github.com",
    }
)
_REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}


def validate_github_source_url(url: str) -> str:
    """
    Validate that the URL is an HTTPS GitHub-controlled source.
    校验 URL 必须为 HTTPS 且属于 GitHub 控制的来源域名。
    """
    normalized = str(url or "").strip()
    if not normalized:
        raise ValueError("GitHub source URL is required")

    parsed = urlparse(normalized)
    host = (parsed.hostname or "").lower()
    scheme = (parsed.scheme or "").lower()

    if scheme != "https":
        raise ValueError("Only HTTPS GitHub source URLs are allowed")
    if host not in _ALLOWED_GITHUB_HOSTS:
        raise ValueError(
            f"Only GitHub source URLs are allowed, got host '{host or '<empty>'}'"
        )
    return normalized


async def open_github_only_stream(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_redirects: int = 5,
) -> httpx.Response:
    """
    Open a streaming GET request while validating every redirect hop stays on GitHub.
    打开流式 GET 请求，并校验每次重定向都仍然停留在 GitHub 白名单域名内。
    """
    current_url = validate_github_source_url(url)

    for _ in range(max_redirects + 1):
        response = await client.send(
            client.build_request("GET", current_url),
            stream=True,
            follow_redirects=False,
        )

        if response.status_code in _REDIRECT_STATUS_CODES:
            location = response.headers.get("location")
            base_url = str(response.url)
            await response.aclose()
            if not location:
                raise ValueError("GitHub source redirect is missing a location header")
            current_url = validate_github_source_url(urljoin(base_url, location))
            continue

        validate_github_source_url(str(response.url))
        return response

    raise ValueError("Too many redirects while opening GitHub source URL")


__all__ = [
    "validate_github_source_url",
    "open_github_only_stream",
]
