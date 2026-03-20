"""
Sanitize HTML stored in system config (tenant legal pages, etc.)
对系统配置中存储的 HTML 进行消毒（企业法律文档等）
"""

from __future__ import annotations

import re
from html import unescape

import nh3

_TAG_RE = re.compile(r"<[^>]+>", re.DOTALL)


def tenant_legal_html_has_meaningful_body(html: str | None) -> bool:
    """
    True if HTML contains visible text (not only empty tags like <p></p>).
    用于判断「站内法律页」是否真有内容，避免空编辑器占位 HTML 误判为有正文。
    """
    if html is None:
        return False
    raw = str(html).strip()
    if not raw:
        return False
    text = _TAG_RE.sub(" ", raw)
    text = unescape(text)
    text = re.sub(r"[\s\u00a0\u200b\ufeff]+", "", text)
    return bool(text)


def sanitize_config_html(value: str) -> str:
    """
    Strip unsafe tags/attributes using ammonia (nh3). Empty input returns empty string.
    使用 nh3（Rust ammonia）剔除不安全标签与属性。
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    cleaned = nh3.clean(value)
    return cleaned or ""


__all__ = [
    "sanitize_config_html",
    "tenant_legal_html_has_meaningful_body",
]
