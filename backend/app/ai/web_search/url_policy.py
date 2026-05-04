"""中文: Web 搜索与 WebResearch 共享的 URL 质量策略。

EN: URL quality policy shared by web search and WebResearch.

中文: 这些 helper 用于识别不能作为答案证据的搜索结果包装页。百度
``/link`` 跳转链接不能拦截，因为 ``fetch_url`` 可以跟随跳转到最终正文页。

EN: These helpers identify search-result wrapper pages that cannot serve as
answer-quality evidence. Baidu redirect links such as ``/link`` are
intentionally not blocked because ``fetch_url`` can follow them to the final
content page.
"""

from __future__ import annotations

from urllib.parse import urlparse

_SEARCH_ENGINE_HOSTS = frozenset({"www.baidu.com", "baidu.com", "m.baidu.com"})
_SEARCH_VERTICAL_HOSTS = frozenset(
    {
        "image.baidu.com",
        "graph.baidu.com",
        "video.baidu.com",
    }
)


def url_is_search_result_wrapper(url: str) -> bool:
    try:
        parsed = urlparse(str(url or "").strip())
        host = (parsed.hostname or "").lower()
    except Exception:  # noqa: BLE001
        return False
    path = str(parsed.path or "").strip().lower()
    if host in _SEARCH_ENGINE_HOSTS:
        return path in {"", "/"} or path.startswith(("/s", "/search"))
    return host in _SEARCH_VERTICAL_HOSTS


__all__ = ["url_is_search_result_wrapper"]
