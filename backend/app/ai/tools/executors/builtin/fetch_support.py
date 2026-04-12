"""
Fetch URL support helpers for builtin tools.
内置工具抓取 URL 辅助函数。
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from app.core.logging import LogManager

logger = LogManager.get_logger("ai.tool.builtin")

# SSRF protection: block access to intranet/cloud metadata hostnames
# SSRF 防护：阻止访问内网/云元数据的主机名
_SSRF_BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "169.254.169.254",
        "metadata.google.internal",
        "metadata.google",
        "100.100.100.200",
    }
)
# Private IP range prefixes (quick check, not exact CIDR)
# 内网 IP 段前缀（快速检查，非精确 CIDR）
_SSRF_PRIVATE_PREFIXES = (
    "10.",
    "172.16.",
    "172.17.",
    "172.18.",
    "172.19.",
    "172.20.",
    "172.21.",
    "172.22.",
    "172.23.",
    "172.24.",
    "172.25.",
    "172.26.",
    "172.27.",
    "172.28.",
    "172.29.",
    "172.30.",
    "172.31.",
    "192.168.",
    "fd",
    "fc",
)

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
_MAIN_CONTENT_SELECTORS = (
    "main",
    "article",
    "[role='main']",
    "#main",
    "#content",
    "#main-content",
    ".main-content",
    ".article-content",
    ".entry-content",
    ".post-content",
    ".markdown-body",
    ".docMainContainer",
    ".docs-body",
)
_TEXT_BLOCK_TAGS = (
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "li",
    "blockquote",
    "pre",
    "td",
    "th",
)
_NOISE_TAGS = (
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "canvas",
    "iframe",
    "form",
    "button",
    "input",
    "select",
    "textarea",
    "nav",
    "footer",
    "header",
    "aside",
)
_NOISE_HINTS = (
    "breadcrumb",
    "cookie",
    "footer",
    "header",
    "menu",
    "nav",
    "navbar",
    "pagination",
    "share",
    "sidebar",
    "social",
    "subscribe",
    "table-of-contents",
    "toc",
    "toolbar",
)


def _normalize_text(text: str) -> str:
    """Collapse whitespace and trim text. / 折叠空白并裁剪文本。"""
    return " ".join((text or "").split())


def _truncate_text(text: str, max_length: int) -> tuple[str, bool]:
    """Truncate text at a readable boundary. / 在较自然的边界截断文本。"""
    if len(text) <= max_length:
        return text, False

    cut = text[:max_length].rstrip()
    breakpoints = [
        cut.rfind("\n\n"),
        cut.rfind(". "),
        cut.rfind("。"),
        cut.rfind("! "),
        cut.rfind("? "),
        cut.rfind("; "),
    ]
    last_break = max(breakpoints)
    if last_break >= max_length // 2:
        cut = cut[: last_break + 1].rstrip()
    return f"{cut}... [truncated]", True


def _classify_fetch_url_error(error_text: str) -> str:
    lowered = str(error_text or "").lower()
    if "request timed out" in lowered:
        return "timeout"
    if any(marker in lowered for marker in ("http 401", "http 403", "http 429")):
        return "blocked_url"
    if "page may block automated access" in lowered or "该页面可能被站点拦截" in lowered:
        return "blocked_url"
    return ""


def _build_fetch_summary(output: str, *, max_length: int = 220) -> str | None:
    lines = [line.strip() for line in str(output or "").splitlines() if line.strip()]
    if not lines:
        return None

    title = ""
    description = ""
    final_url = ""
    for line in lines:
        if not final_url and line.startswith("Content from "):
            final_url = line.removeprefix("Content from ").rstrip(":").strip()
        elif not title and line.startswith("Title: "):
            title = line.removeprefix("Title: ").strip()
        elif not description and line.startswith("Description: "):
            description = line.removeprefix("Description: ").strip()

    summary = ""
    if title and description:
        summary = f"{title} - {description}"
    elif title:
        summary = title
    elif description:
        summary = description
    elif final_url:
        summary = f"Fetched {final_url}"
    else:
        summary = lines[0]

    normalized, _ = _truncate_text(_normalize_text(summary), max_length)
    return normalized or None


def _extract_fetch_summary_payload(
    *,
    requested_url: str,
    output: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    requested = str(requested_url or "").strip()
    final_url = ""
    title = ""
    description = ""
    summary = None
    error_text = str(error or "").strip()
    error_type = _classify_fetch_url_error(error_text) if error_text else ""

    lines = [line.strip() for line in str(output or "").splitlines() if line.strip()]
    for line in lines:
        if not final_url and line.startswith("Content from "):
            final_url = line.removeprefix("Content from ").rstrip(":").strip()
        elif not requested and line.startswith("Redirected from: "):
            requested = line.removeprefix("Redirected from: ").strip()
        elif not title and line.startswith("Title: "):
            title = line.removeprefix("Title: ").strip()
        elif not description and line.startswith("Description: "):
            description = line.removeprefix("Description: ").strip()

    if output:
        summary = _build_fetch_summary(output)

    if not final_url and error_text:
        for marker in ("while fetching ", "found at ", "URL: "):
            if marker not in error_text:
                continue
            final_url = error_text.split(marker, 1)[1].split(" ", 1)[0].strip(" .)")
            if final_url:
                break
        if "(title:" in error_text and not title:
            title = error_text.split("(title:", 1)[1].split(")", 1)[0].strip()

    if not requested:
        requested = final_url

    return {
        "fetch_url": True,
        "ok": not error_text,
        "error_type": error_type,
        "requested_url": requested or None,
        "final_url": final_url or None,
        "title": title or None,
        "description": description or None,
        "summary": summary,
    }


def _extract_title_from_html(html: str) -> str:
    lowered = (html or "").lower()
    title_start = lowered.find("<title")
    if title_start == -1:
        return ""
    title_end = lowered.find("</title>", title_start)
    if title_end == -1:
        return ""
    tag_end = lowered.find(">", title_start)
    if tag_end == -1 or tag_end >= title_end:
        return ""
    return _normalize_text((html or "")[tag_end + 1 : title_end])


def _extract_declared_charset(content_type: str) -> str:
    content_type = (content_type or "").lower()
    if "charset=" not in content_type:
        return ""
    parts = content_type.split("charset=", 1)[1]
    charset = parts.split(";")[0].strip().strip('"').strip("'")
    return charset


def _extract_meta_charset(raw_bytes: bytes) -> str:
    head = raw_bytes[:4096].decode("ascii", errors="ignore").lower()
    match = re.search(r'charset=["\']?([a-z0-9_\-]+)', head)
    if match:
        return match.group(1).strip().lower()
    return ""


def _detect_best_effort_charset(raw_bytes: bytes) -> str:
    head = raw_bytes[:4096].decode("ascii", errors="ignore").lower()
    for pattern in ("charset=gb2312", "charset=gbk", "charset=gb18030"):
        match = re.search(pattern, head, re.IGNORECASE)
        if match:
            return pattern.split("charset=")[1]
    return ""


def _decode_fetch_response_text(resp: Any, *, content_type: str) -> str:
    raw_bytes = resp.content or b""
    declared = _extract_declared_charset(content_type)
    if declared:
        try:
            return raw_bytes.decode(declared, errors="replace")
        except (LookupError, UnicodeDecodeError):
            pass
    meta_charset = _extract_meta_charset(raw_bytes)
    if meta_charset:
        try:
            return raw_bytes.decode(meta_charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            pass

    # Best-effort fallback for common CN encodings / 常见中文编码兜底
    candidate_encodings = []

    def _append_candidate(encoding: str) -> None:
        if encoding and encoding not in candidate_encodings:
            candidate_encodings.append(encoding)

    _append_candidate(_detect_best_effort_charset(raw_bytes))
    _append_candidate("utf-8")

    for encoding in candidate_encodings:
        try:
            return raw_bytes.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue

    return raw_bytes.decode("utf-8", errors="replace")


def _remove_noise_nodes(soup: Any) -> None:
    """Drop common non-content nodes. / 删除常见非正文节点。"""
    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    for node in soup.find_all(True):
        if not isinstance(getattr(node, "attrs", None), dict):
            continue

        if node.has_attr("hidden") or node.get("aria-hidden") == "true":
            node.decompose()
            continue

        style = (node.get("style") or "").lower()
        if "display:none" in style or "visibility:hidden" in style:
            node.decompose()
            continue

        if node.name not in {"div", "section", "ul", "ol"}:
            continue

        hints = " ".join(
            [
                node.get("id", ""),
                " ".join(node.get("class", [])),
            ]
        ).lower()
        if hints and any(noise in hints for noise in _NOISE_HINTS):
            node.decompose()


def _score_content_node(node: Any) -> int:
    """Rough heuristic for selecting the main content container. / 粗略评分主内容容器。"""
    paragraph_texts = [
        _normalize_text(item.get_text(" ", strip=True))
        for item in node.find_all(["p", "li"], limit=80)
    ]
    paragraph_chars = sum(len(text) for text in paragraph_texts if text)
    heading_count = len(node.find_all(["h1", "h2", "h3"], limit=16))
    link_chars = sum(
        len(_normalize_text(link.get_text(" ", strip=True)))
        for link in node.find_all("a", limit=120)
    )
    return paragraph_chars + heading_count * 50 - link_chars


def _pick_main_content_node(soup: Any) -> Any:
    for selector in _MAIN_CONTENT_SELECTORS:
        node = soup.select_one(selector)
        if node is not None:
            return node

    candidates = soup.find_all(["article", "main", "section", "div"], limit=50)
    if not candidates:
        return soup.body or soup

    scored = sorted(candidates, key=_score_content_node, reverse=True)
    best = scored[0]
    if _score_content_node(best) <= 0:
        return soup.body or soup
    return best


def _collect_text_blocks(node: Any, *, max_blocks: int = 120) -> list[str]:
    blocks: list[str] = []
    for tag in node.find_all(_TEXT_BLOCK_TAGS):
        text = _normalize_text(tag.get_text(" ", strip=True))
        if not text:
            continue
        if blocks and text == blocks[-1]:
            continue
        blocks.append(text)
        if len(blocks) >= max_blocks:
            break
    return blocks


def _extract_meta_description(soup: Any) -> str:
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return _normalize_text(meta.get("content"))
    meta = soup.find("meta", attrs={"property": "og:description"})
    if meta and meta.get("content"):
        return _normalize_text(meta.get("content"))
    return ""


def _extract_readable_page(html: str) -> dict[str, Any]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    _remove_noise_nodes(soup)
    main_node = _pick_main_content_node(soup)

    title = _normalize_text(_extract_title_from_html(html))
    description = _extract_meta_description(soup)
    text_blocks = _collect_text_blocks(main_node) if main_node else []
    body = "\n\n".join(text_blocks)

    return {
        "title": title,
        "description": description,
        "body": body,
    }


def _format_html_fetch_output(
    *,
    requested_url: str,
    final_url: str,
    page: dict[str, Any],
    max_length: int,
) -> str:
    title = page.get("title", "") or ""
    description = page.get("description", "") or ""
    lines = [f"Content from {final_url}:"]
    if final_url and requested_url and final_url != requested_url:
        lines.append(f"Redirected from: {requested_url}")
    if title:
        lines.append(f"Title: {title}")
    if description:
        lines.append(f"Description: {description}")

    prefix = "\n".join(lines).strip()
    body = page.get("body", "") or ""
    if not body:
        return (
            f"Error: No readable main content found at {final_url}. "
            "The page may require JavaScript or block automated reading."
        )

    remaining = max(max_length - len(prefix) - 2, 200)
    excerpt, _ = _truncate_text(body, remaining)
    return f"{prefix}\n\n{excerpt}"


def _is_ssrf_blocked(url: str) -> str | None:
    """Check if URL points to intranet/cloud metadata, return error message or None. / 检查 URL 是否指向内网/云元数据，返回错误消息或 None。"""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host:
            return "Invalid URL: no hostname"
        if host in _SSRF_BLOCKED_HOSTS:
            return f"Blocked: requests to {host} are not allowed"
        if host.startswith(_SSRF_PRIVATE_PREFIXES):
            return f"Blocked: requests to private network ({host}) are not allowed"
        # Block non-HTTP(S) protocols / 阻止非 HTTP(S) 协议
        if parsed.scheme not in ("http", "https"):
            return f"Blocked: only http/https URLs are allowed, got {parsed.scheme}"
    except Exception:
        return "Invalid URL"
    return None


async def fetch_url_result(url: str = "", max_length: int = 5000) -> tuple[bool, str]:
    """
    Fetch URL; returns (success, text).
    On failure, text is the error detail for ToolResult.error (no "Error:" prefix).
    """
    if not url:
        return False, "url parameter is required"

    ssrf_err = _is_ssrf_blocked(url)
    if ssrf_err:
        return False, ssrf_err

    import httpx

    max_length = min(max(500, max_length), 20000)
    hint = (
        " This page may block automated access; try another candidate URL from "
        "search results with fetch_url."
    )
    hint_zh = (
        " 该页面可能被站点拦截，请从搜索结果中换其他候选 URL 后用 fetch_url 重试。"
    )

    try:
        timeout = httpx.Timeout(20.0, connect=10.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=_DEFAULT_WEB_HEADERS,
        ) as client:
            resp = await client.get(url)

        final_url = str(resp.url)
        content_type = (resp.headers.get("content-type") or "").lower()
        raw_text = _decode_fetch_response_text(resp, content_type=content_type)

        if resp.status_code >= 400:
            page = _extract_readable_page(raw_text) if raw_text else {}
            title = page.get("title") if page else ""
            message = f"HTTP {resp.status_code} while fetching {final_url}"
            if title:
                message += f" (title: {title})"
            if resp.status_code in (401, 403, 429):
                message += hint + hint_zh
            return False, message

        if "html" in content_type or "<html" in raw_text[:1000].lower():
            page = _extract_readable_page(raw_text)
            formatted = _format_html_fetch_output(
                requested_url=url,
                final_url=final_url,
                page=page,
                max_length=max_length,
            )
            if formatted.strip().startswith("Error:"):
                return False, formatted.strip()[len("Error:") :].strip() + hint_zh
            return True, formatted

        text, _ = _truncate_text(_normalize_text(raw_text), max_length)
        if text:
            return True, f"Content from {final_url}:\n\n{text}"
        return False, f"No readable content found at {final_url}"

    except httpx.TimeoutException:
        return False, f"Request timed out for URL: {url}"
    except httpx.HTTPError as exc:
        logger.warning("fetch_url request error for {}: {}", url, exc)
        return False, f"Failed to fetch URL - {exc}"
    except Exception as exc:
        logger.warning("fetch_url failed for {}: {}", url, exc)
        return False, f"Failed to fetch URL - {exc}"


__all__ = [
    "fetch_url_result",
    "_build_fetch_summary",
    "_extract_fetch_summary_payload",
]
