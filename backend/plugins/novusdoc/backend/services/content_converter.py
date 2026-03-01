"""
Tiptap JSON → 纯文本 / HTML 转换器

最小可用实现，支持常见节点类型。
后续可按需扩展更多节点类型和 mark 处理。
"""

from __future__ import annotations

from typing import Any


def tiptap_to_text(doc: dict[str, Any] | None) -> str:
    """Tiptap JSON → 纯文本（全文搜索用）"""
    if not doc or not isinstance(doc, dict):
        return ""
    content = doc.get("content", [])
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for node in content:
        _extract_text(node, parts)
    return "\n".join(parts)


def tiptap_to_html(doc: dict[str, Any] | None) -> str:
    """Tiptap JSON → HTML（导出/渲染缓存用）"""
    if not doc or not isinstance(doc, dict):
        return ""
    content = doc.get("content", [])
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for node in content:
        parts.append(_render_node(node))
    return "".join(parts)


def count_words(text: str) -> int:
    """统计字数（中文按字，英文按词）"""
    if not text:
        return 0
    count = 0
    in_word = False
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff" or "\u3400" <= ch <= "\u4dbf":
            count += 1
            in_word = False
        elif ch.isalnum():
            if not in_word:
                count += 1
                in_word = True
        else:
            in_word = False
    return count


# ── internal helpers ──

_BLOCK_TAGS: dict[str, tuple[str, str]] = {
    "paragraph": ("<p>", "</p>"),
    "heading": ("<h{level}>", "</h{level}>"),
    "blockquote": ("<blockquote>", "</blockquote>"),
    "bulletList": ("<ul>", "</ul>"),
    "orderedList": ("<ol>", "</ol>"),
    "listItem": ("<li>", "</li>"),
    "taskList": ("<ul>", "</ul>"),
    "taskItem": ("<li>", "</li>"),
    "codeBlock": ("<pre><code>", "</code></pre>"),
    "horizontalRule": ("<hr/>", ""),
    "table": ("<table>", "</table>"),
    "tableRow": ("<tr>", "</tr>"),
    "tableCell": ("<td>", "</td>"),
    "tableHeader": ("<th>", "</th>"),
}

_MARK_TAGS: dict[str, tuple[str, str]] = {
    "bold": ("<strong>", "</strong>"),
    "italic": ("<em>", "</em>"),
    "underline": ("<u>", "</u>"),
    "strike": ("<s>", "</s>"),
    "code": ("<code>", "</code>"),
    "highlight": ("<mark>", "</mark>"),
}


def _extract_text(node: dict[str, Any], parts: list[str]) -> None:
    """递归提取纯文本"""
    node_type = node.get("type", "")

    if node_type == "text":
        text = node.get("text", "")
        if text:
            parts.append(text)
        return

    if node_type == "hardBreak":
        parts.append("\n")
        return

    if node_type == "image":
        alt = (node.get("attrs") or {}).get("alt", "")
        if alt:
            parts.append(alt)
        return

    children = node.get("content", [])
    if isinstance(children, list):
        for child in children:
            _extract_text(child, parts)

    if node_type in ("paragraph", "heading", "listItem", "taskItem", "blockquote"):
        parts.append("\n")


def _render_node(node: dict[str, Any]) -> str:
    """递归渲染 HTML"""
    node_type = node.get("type", "")

    if node_type == "text":
        text = _escape_html(node.get("text", ""))
        marks = node.get("marks", [])
        for mark in marks:
            mark_type = mark.get("type", "")
            tags = _MARK_TAGS.get(mark_type)
            if tags:
                text = f"{tags[0]}{text}{tags[1]}"
            elif mark_type == "link":
                href = _escape_html((mark.get("attrs") or {}).get("href", ""))
                text = f'<a href="{href}">{text}</a>'
        return text

    if node_type == "hardBreak":
        return "<br/>"

    if node_type == "horizontalRule":
        return "<hr/>"

    if node_type == "image":
        attrs = node.get("attrs") or {}
        src = _escape_html(attrs.get("src", ""))
        alt = _escape_html(attrs.get("alt", ""))
        return f'<img src="{src}" alt="{alt}"/>'

    # block nodes
    tags = _BLOCK_TAGS.get(node_type)
    if tags:
        open_tag = tags[0]
        close_tag = tags[1]
        if node_type == "heading":
            level = (node.get("attrs") or {}).get("level", 1)
            open_tag = open_tag.format(level=level)
            close_tag = close_tag.format(level=level)
    else:
        open_tag = f"<div>"
        close_tag = "</div>"

    children = node.get("content", [])
    inner = ""
    if isinstance(children, list):
        inner = "".join(_render_node(child) for child in children)

    return f"{open_tag}{inner}{close_tag}"


def _escape_html(text: str) -> str:
    """最小 HTML 转义"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
