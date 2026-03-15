"""NovusDoc export API handler / NovusDoc 导出 API 处理器"""

from __future__ import annotations

import html
import json
import logging
import re
from io import BytesIO
from urllib.parse import quote

from starlette.responses import Response

from .documents import _resolve_tenant_id

logger = logging.getLogger(__name__)

# Emoji/symbol ranges that xhtml2pdf/reportlab often cannot render
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F700-\U0001F77F"  # alchemical symbols
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U00002702-\U000027B0"  # dingbats
    "]+",
    flags=re.UNICODE,
)


def _sanitize_html_for_pdf(html_content: str) -> str:
    """Strip CSS/HTML that xhtml2pdf cannot render / 移除 xhtml2pdf 不支持的 CSS/HTML"""
    s = html_content
    # 移除 colgroup/col 标签（xhtml2pdf 不支持）
    s = re.sub(r"<colgroup[^>]*>.*?</colgroup>", "", s, flags=re.DOTALL)
    s = re.sub(r"<col[^>]*/?>", "", s)
    # 简化表格样式
    s = re.sub(r"border-collapse:\s*collapse;?", "", s)
    s = re.sub(r"background-color:\s*#[0-9a-fA-F]+;?", "", s)
    s = re.sub(r"text-align:\s*justify;?", "text-align: left;", s)
    return s


def _content_disposition_attachment(filename: str) -> str:
    """Build Content-Disposition header, RFC 5987 for non-ASCII filenames.
    HTTP headers must be Latin-1, so use filename*=UTF-8''<percent-encoded> for Unicode.
    """
    try:
        filename.encode("ascii")
        return f'attachment; filename="{filename}"'
    except UnicodeEncodeError:
        encoded = quote(filename, safe="")
        return f"attachment; filename=\"document\"; filename*=UTF-8''{encoded}"


def _strip_emojis_for_pdf(text: str) -> str:
    """Remove emojis that xhtml2pdf/reportlab cannot render."""
    return _EMOJI_PATTERN.sub("", text)


def _html_to_pdf(html_content: str, title: str) -> bytes:
    """Convert HTML to PDF using xhtml2pdf / 使用 xhtml2pdf 将 HTML 转为 PDF"""
    from xhtml2pdf import pisa

    # Strip emojis - reportlab default fonts cannot render them
    html_no_emoji = _strip_emojis_for_pdf(html_content)
    clean_title = _strip_emojis_for_pdf(title)
    # Sanitize TipTap HTML: remove colgroup/col, simplify CSS
    clean_html = _sanitize_html_for_pdf(html_no_emoji)
    wrapped = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>{html.escape(clean_title)}</title>
<style>
  body {{ font-family: STSong-Light, Helvetica, sans-serif; font-size: 12px; }}
  table {{ width: 100%; border: 1px solid #000; }}
  td, th {{ border: 1px solid #000; padding: 4px; }}
  blockquote {{ border-left: 2px solid #666; padding-left: 8px; margin: 8px 0; }}
</style>
</head><body>{clean_html}</body></html>"""
    out = BytesIO()
    pisa_status = pisa.CreatePDF(wrapped, dest=out, encoding="utf-8")
    if pisa_status.err:
        err_detail = getattr(pisa_status, "log", None) or str(pisa_status)
        logger.warning("xhtml2pdf CreatePDF err=True: %s", err_detail)
        raise RuntimeError("PDF generation failed")  # noqa: TRY003
    return out.getvalue()


async def export_doc(request, db, ctx):
    tenant_id = _resolve_tenant_id(request, ctx)

    doc_id = int(request.path_params["doc_id"])
    fmt = request.query_params.get("format", "html")

    from ..services.document_service import get_document
    doc = await get_document(db, tenant_id, doc_id)
    if not doc:
        return {"error": "Document not found", "status_code": 404}

    title = doc["title"]
    # Sanitize filename: remove path separators / 清理文件名中的路径分隔符
    safe_title = re.sub(r'[/\\:*?"<>|]', "_", title) or "document"

    if fmt in ("markdown", "md"):
        text = doc.get("content_text", "")
        return Response(
            content=text,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": _content_disposition_attachment(f"{safe_title}.md")},
        )

    if fmt == "pdf":
        html_raw = doc.get("content_html") or f"<h1>{title}</h1><p>{doc.get('content_text', '')}</p>"
        try:
            pdf_bytes = _html_to_pdf(html_raw, title)
        except Exception as exc:
            logger.exception("PDF export failed for doc %s: %s", doc_id, exc)
            return Response(
                content=json.dumps({
                    "error": "PDF export failed. Try HTML or Markdown format.",
                    "detail": str(exc)[:200],
                }),
                media_type="application/json",
                status_code=500,
            )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": _content_disposition_attachment(f"{safe_title}.pdf")},
        )

    html_content = doc.get("content_html") or f"<h1>{title}</h1><p>{doc.get('content_text', '')}</p>"
    return Response(
        content=html_content,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": _content_disposition_attachment(f"{safe_title}.html")},
    )
