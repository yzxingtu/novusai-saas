"""NovusDoc export API handler / NovusDoc 导出 API 处理器"""

from __future__ import annotations

import html
import json
import re
from io import BytesIO
from urllib.parse import quote

from starlette.responses import Response

from app.core.logging import get_logger

from .documents import _resolve_tenant_id

logger = get_logger(__name__)

# Emoji/symbol ranges that xhtml2pdf/reportlab often cannot render / 表情与符号区间（PDF 难渲染）
_EMOJI_PATTERN = (
    "["
    "\U0001f1e0-\U0001f1ff"  # flags / 旗帜区
    "\U0001f300-\U0001f5ff"  # symbols & pictographs / 符号与象形
    "\U0001f600-\U0001f64f"  # emoticons / 表情
    "\U0001f680-\U0001f6ff"  # transport & map symbols / 交通与地图符号
    "\U0001f700-\U0001f77f"  # alchemical symbols / 炼金符号
    "\U0001f900-\U0001f9ff"  # supplemental symbols / 补充符号
    "\U00002702-\U000027b0"  # dingbats / 装饰符号
    "]+"
)


def _sanitize_html_for_pdf(html_content: str) -> str:
    """Strip CSS/HTML that xhtml2pdf cannot render / 移除 xhtml2pdf 不支持的 CSS/HTML"""
    s = html_content
    # 移除 colgroup/col 标签（xhtml2pdf 不支持）
    s = re.sub(r"<colgroup[^>]*>.*?</colgroup>", "", s, flags=re.DOTALL)
    s = re.sub(r"<col[^>]*/?>", "", s)
    # 简化表格样式 / simplify table-related CSS
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
    return re.sub(_EMOJI_PATTERN, "", text, flags=re.UNICODE)


def _html_to_pdf(html_content: str, title: str) -> bytes:
    """Convert HTML to PDF using xhtml2pdf / 使用 xhtml2pdf 将 HTML 转为 PDF"""
    from xhtml2pdf import pisa

    # Strip emojis - reportlab default fonts cannot render them / 去掉表情（默认字体不支持）
    html_no_emoji = _strip_emojis_for_pdf(html_content)
    clean_title = _strip_emojis_for_pdf(title)
    # Sanitize TipTap HTML: remove colgroup/col, simplify CSS / 清理 TipTap 输出的 HTML/CSS
    clean_html = _sanitize_html_for_pdf(html_no_emoji)
    wrapped = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>{html.escape(clean_title)}</title>
<style>
  body {{ font-family: STSong-Light, Helvetica, sans-serif; font-size: 12px; }}
  table {{ width: 100%; border: 1px solid rgb(0, 0, 0); }}
  td, th {{ border: 1px solid rgb(0, 0, 0); padding: 4px; }}
  blockquote {{ border-left: 2px solid rgb(102, 102, 102); padding-left: 8px; margin: 8px 0; }}
</style>
</head><body>{clean_html}</body></html>"""
    out = BytesIO()
    pisa_status = pisa.CreatePDF(wrapped, dest=out, encoding="utf-8")
    if pisa_status.err:
        err_detail = getattr(pisa_status, "log", None) or str(pisa_status)
        logger.warning("xhtml2pdf CreatePDF err=True: {}", err_detail)
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
            headers={
                "Content-Disposition": _content_disposition_attachment(
                    f"{safe_title}.md"
                )
            },
        )

    if fmt == "pdf":
        html_raw = (
            doc.get("content_html")
            or f"<h1>{title}</h1><p>{doc.get('content_text', '')}</p>"
        )
        try:
            pdf_bytes = _html_to_pdf(html_raw, title)
        except Exception as exc:
            logger.exception("PDF export failed for doc {}: {}", doc_id, exc)
            return Response(
                content=json.dumps(
                    {
                        "error": "PDF export failed. Try HTML or Markdown format.",
                        "detail": str(exc)[:200],
                    }
                ),
                media_type="application/json",
                status_code=500,
            )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": _content_disposition_attachment(
                    f"{safe_title}.pdf"
                )
            },
        )

    html_content = (
        doc.get("content_html")
        or f"<h1>{title}</h1><p>{doc.get('content_text', '')}</p>"
    )
    return Response(
        content=html_content,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": _content_disposition_attachment(f"{safe_title}.html")
        },
    )
