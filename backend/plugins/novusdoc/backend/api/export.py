"""
NovusDoc Free 版导出 API handlers（HTML / Markdown）

复用 content_converter 已有的 tiptap_to_html 和 tiptap_to_text 能力。
返回文件下载响应（Content-Disposition: attachment）。
"""

from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger("plugin.novusdoc.api")


def _safe_int(val, name: str = "id") -> tuple[int | None, dict | None]:
    if val is None:
        return None, {"error": f"{name} required", "code": 4001}
    try:
        return int(val), None
    except (ValueError, TypeError):
        return None, {"error": f"invalid {name}", "code": 4001}


async def export_html(request, db, ctx):
    """GET /docs/{doc_id}/export/html — 导出 HTML 文件"""
    from fastapi.responses import Response

    from ..services.document_service import get_document

    tenant_id = ctx.get_current_tenant_id()
    if not tenant_id:
        return {"error": "tenant_id required", "code": 4010}

    doc_id, err = _safe_int(request.path_params.get("doc_id"), "doc_id")
    if err:
        return err

    doc = await get_document(db, tenant_id, doc_id)
    if not doc:
        return {"error": "document not found", "code": 4040, "status_code": 404}

    title = doc.get("title", "") or "untitled"
    html_content = doc.get("content_html", "")

    if not html_content and doc.get("content"):
        from ..services.content_converter import tiptap_to_html
        html_content = tiptap_to_html(doc["content"])

    full_html = (
        "<!DOCTYPE html>\n"
        "<html lang=\"zh-CN\">\n"
        "<head>\n"
        f"  <meta charset=\"utf-8\">\n"
        f"  <title>{_escape_html(title)}</title>\n"
        "  <style>body{font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem;line-height:1.6;}"
        "img{max-width:100%;height:auto;}pre{background:#f5f5f5;padding:1rem;border-radius:8px;overflow-x:auto;}"
        "blockquote{border-left:3px solid #8B5CF6;padding-left:1rem;margin-left:0;color:#666;}"
        "table{border-collapse:collapse;width:100%;}td,th{border:1px solid #ddd;padding:8px 12px;text-align:left;}"
        "th{background:#f5f5f5;font-weight:600;}</style>\n"
        "</head>\n"
        f"<body>\n<h1>{_escape_html(title)}</h1>\n{html_content}\n</body>\n"
        "</html>"
    )

    safe_filename = _safe_filename(title) + ".html"
    return Response(
        content=full_html,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
        },
    )


async def export_markdown(request, db, ctx):
    """GET /docs/{doc_id}/export/markdown — 导出 Markdown 文件"""
    from fastapi.responses import Response

    from ..services.document_service import get_document

    tenant_id = ctx.get_current_tenant_id()
    if not tenant_id:
        return {"error": "tenant_id required", "code": 4010}

    doc_id, err = _safe_int(request.path_params.get("doc_id"), "doc_id")
    if err:
        return err

    doc = await get_document(db, tenant_id, doc_id)
    if not doc:
        return {"error": "document not found", "code": 4040, "status_code": 404}

    title = doc.get("title", "") or "untitled"
    content = doc.get("content")

    if content:
        md_content = _tiptap_to_markdown(content)
    else:
        md_content = doc.get("content_text", "") or ""

    full_md = f"# {title}\n\n{md_content}"

    safe_filename = _safe_filename(title) + ".md"
    return Response(
        content=full_md,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
        },
    )


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _safe_filename(title: str) -> str:
    import re
    name = re.sub(r'[\\/:*?"<>|]', "_", title.strip())
    return name[:100] if name else "document"


def _tiptap_to_markdown(doc: dict) -> str:
    """Tiptap JSON → Markdown（最小可用实现）"""
    content = doc.get("content", [])
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for node in content:
        _render_md_node(node, parts, depth=0)
    return "\n".join(parts)


def _render_md_node(node: dict, parts: list[str], depth: int = 0) -> None:
    node_type = node.get("type", "")

    if node_type == "text":
        text = node.get("text", "")
        marks = node.get("marks", [])
        for mark in marks:
            mt = mark.get("type", "")
            if mt == "bold":
                text = f"**{text}**"
            elif mt == "italic":
                text = f"*{text}*"
            elif mt == "code":
                text = f"`{text}`"
            elif mt == "strike":
                text = f"~~{text}~~"
            elif mt == "link":
                href = (mark.get("attrs") or {}).get("href", "")
                text = f"[{text}]({href})"
        parts.append(text)
        return

    if node_type == "hardBreak":
        parts.append("  \n")
        return

    if node_type == "horizontalRule":
        parts.append("\n---\n")
        return

    if node_type == "heading":
        level = (node.get("attrs") or {}).get("level", 1)
        prefix = "#" * level + " "
        inner = _collect_inline(node)
        parts.append(f"\n{prefix}{inner}\n")
        return

    if node_type == "paragraph":
        inner = _collect_inline(node)
        parts.append(f"\n{inner}\n")
        return

    if node_type == "blockquote":
        inner = _collect_inline(node)
        parts.append(f"\n> {inner}\n")
        return

    if node_type == "codeBlock":
        lang = (node.get("attrs") or {}).get("language", "")
        inner = _collect_inline(node)
        parts.append(f"\n```{lang}\n{inner}\n```\n")
        return

    if node_type == "bulletList":
        for item in node.get("content", []):
            inner = _collect_inline(item)
            parts.append(f"- {inner}")
        parts.append("")
        return

    if node_type == "orderedList":
        for i, item in enumerate(node.get("content", []), 1):
            inner = _collect_inline(item)
            parts.append(f"{i}. {inner}")
        parts.append("")
        return

    if node_type == "taskList":
        for item in node.get("content", []):
            checked = (item.get("attrs") or {}).get("checked", False)
            mark = "[x]" if checked else "[ ]"
            inner = _collect_inline(item)
            parts.append(f"- {mark} {inner}")
        parts.append("")
        return

    if node_type == "image":
        attrs = node.get("attrs") or {}
        src = attrs.get("src", "")
        alt = attrs.get("alt", "")
        parts.append(f"\n![{alt}]({src})\n")
        return

    children = node.get("content", [])
    if isinstance(children, list):
        for child in children:
            _render_md_node(child, parts, depth + 1)


def _collect_inline(node: dict) -> str:
    parts: list[str] = []
    for child in node.get("content", []):
        _render_md_node(child, parts)
    return "".join(parts)
