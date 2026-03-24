"""
Resolve chat attachment image URLs to data URLs for LLM multimodal APIs.
将对话附件图片 URL 解析为 data URL，供 LLM 多模态 API 使用。

Relative paths like ``/api/public/attachments/{id}/access`` or
``/api/public/attachments/{id}/image`` are not fetchable by vendor APIs; we
read bytes from storage (tenant-scoped) or use HTTP fallback.
"""

from __future__ import annotations

import base64
import re
from urllib.parse import parse_qs, urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.tools.security import SSRFBlockedError, UrlValidator
from app.core.config import settings
from app.core.logging import LogManager
from app.enums.attachment import AttachmentVisibility
from app.services.tenant.attachment_download_service import AttachmentDownloadService
from app.storage import storage_manager

logger = LogManager.get_logger("ai")

_ATTACHMENT_URL_RE = re.compile(
    r"/api/public/attachments/(\d+)/(?:access|image)",
    re.IGNORECASE,
)

# Max image body when resolving for LLM (bytes) / 上文为英文说明 / English above
_IMAGE_MAX_BYTES: int = 20 * 1024 * 1024
_FETCH_TIMEOUT_SEC: float = 45.0


def _coerce_attachment_id(raw: object) -> int | None:
    """Normalize positive attachment IDs from payloads or URLs / 规范化附件 ID。"""
    if isinstance(raw, int):
        return raw if raw > 0 else None
    text = str(raw or "").strip()
    if not text or not text.isdigit():
        return None
    value = int(text)
    return value if value > 0 else None


def _attachment_id_from_url(raw: str) -> tuple[int | None, str | None]:
    """
    Parse attachment id and optional JWT token from path or full URL.
    """
    s = (raw or "").strip()
    if not s:
        return None, None
    parsed = urlparse(s if "://" in s else f"http://_ignored{s if s.startswith('/') else '/' + s}")
    path = parsed.path or ""
    m = _ATTACHMENT_URL_RE.search(path)
    if not m:
        return None, None
    aid = int(m.group(1))
    qs = parse_qs(parsed.query or "")
    token_list = qs.get("token")
    token = token_list[0] if token_list else None
    return aid, token


async def _read_attachment_bytes_via_db(
    db: AsyncSession,
    tenant_id: int | None,
    attachment_id: int,
    token: str | None,
    *,
    max_bytes: int,
) -> tuple[bytes, str] | None:
    """
    Load attachment bytes using DB + storage driver (supports private files when
    tenant_id matches attachment owner, or token is valid).
    """
    try:
        svc = AttachmentDownloadService(db, tenant_id=tenant_id)
        att = await svc.get_attachment(attachment_id)
        if att.visibility == AttachmentVisibility.PUBLIC.value:
            pass
        elif token:
            await svc.validate_access(att, token)
        elif tenant_id is not None:
            # Private, no JWT: scoped get_attachment already matched tenant / 上文为英文说明 / English above
            pass
        else:
            await svc.validate_access(att, None)
    except Exception as exc:
        logger.warning(
            "LLM image: attachment access denied or missing id={} err={}",
            attachment_id,
            exc,
        )
        return None
    if att.size is not None and int(att.size) > max_bytes:
        logger.warning(
            "LLM image: attachment too large (declared) id={} size={}",
            attachment_id,
            att.size,
        )
        return None
    try:
        storage_config = await svc._resolve_storage_config_for_attachment(att)
        driver = storage_manager.get_driver(storage_config)
        bio = await driver.get(att.path)
        data = bio.read() if hasattr(bio, "read") else bytes(bio)
    except Exception as exc:
        logger.warning(
            "LLM image: storage read failed id={} err={}",
            attachment_id,
            exc,
        )
        return None
    if len(data) > max_bytes:
        logger.warning(
            "LLM image: body too large id={} len={}",
            attachment_id,
            len(data),
        )
        return None
    mime = (att.mime_type or "").strip() or "image/png"
    if not mime.startswith("image/"):
        mime = "image/png"
    return data, mime


async def _fetch_url_bytes(url: str, *, max_bytes: int) -> tuple[bytes, str] | None:
    """HTTP(S) GET with SSRF validation."""
    try:
        await UrlValidator.validate(url)
    except SSRFBlockedError as e:
        logger.warning("LLM image: URL blocked (SSRF): {}", e)
        return None
    try:
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT_SEC, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            cl = resp.headers.get("content-length")
            if cl and cl.strip().isdigit() and int(cl) > max_bytes:
                return None
            data = resp.content
            if len(data) > max_bytes:
                return None
            ctype = (resp.headers.get("content-type") or "").split(";")[0].strip()
            mime = ctype if ctype.startswith("image/") else "image/png"
            return data, mime
    except Exception as exc:
        logger.warning("LLM image: HTTP fetch failed url={} err={}", url, exc)
        return None


async def resolve_image_url_for_llm(
    raw_url: str,
    mime_hint: str | None,
    *,
    db: AsyncSession | None,
    tenant_id: int | None,
    attachment_id: object = None,
    max_bytes: int = _IMAGE_MAX_BYTES,
) -> str | None:
    """
    Return a ``data:image/...;base64,...`` URL suitable for OpenAI ``image_url``,
    or None if resolution fails.
    """
    url = (raw_url or "").strip()
    hint_attachment_id = _coerce_attachment_id(attachment_id)
    if not url and hint_attachment_id is None:
        return None
    if url.startswith("data:image"):
        return url

    parsed_attachment_id, token = _attachment_id_from_url(url)
    aid = hint_attachment_id or parsed_attachment_id
    if (
        hint_attachment_id is not None
        and parsed_attachment_id is not None
        and hint_attachment_id != parsed_attachment_id
    ):
        logger.warning(
            "LLM image: attachment_id hint/url mismatch hint={} parsed={} url={}",
            hint_attachment_id,
            parsed_attachment_id,
            url[:160],
        )
        token = None

    if db is not None and aid is not None:
        got = await _read_attachment_bytes_via_db(
            db, tenant_id, aid, token, max_bytes=max_bytes,
        )
        if got:
            data, mime = got
            b64 = base64.b64encode(data).decode("ascii")
            return f"data:{mime};base64,{b64}"

    if not url:
        return None

    # Relative app path → internal HTTP (public files or URL with token) / 上文为英文说明 / English above
    if url.startswith("/"):
        base = (settings.APP_INTERNAL_BASE_URL or "").strip().rstrip("/")
        if base:
            full = f"{base}{url}"
            got = await _fetch_url_bytes(full, max_bytes=max_bytes)
            if got:
                data, mime = got
                b64 = base64.b64encode(data).decode("ascii")
                return f"data:{mime};base64,{b64}"
        logger.warning(
            "LLM image: relative URL and APP_INTERNAL_BASE_URL unset or fetch failed: {}",
            url[:120],
        )
        return None

    if url.lower().startswith("http://") or url.lower().startswith("https://"):
        got = await _fetch_url_bytes(url, max_bytes=max_bytes)
        if got:
            data, mime = got
            if mime_hint and mime_hint.startswith("image/"):
                mime = mime_hint
            b64 = base64.b64encode(data).decode("ascii")
            return f"data:{mime};base64,{b64}"
        return None

    return None


__all__ = ["resolve_image_url_for_llm"]
