"""URL and attachment parsing helpers for AI runtime flows."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from app.ai.text_semantics_tokens import safe_positive_int


def extract_public_attachment_reference(
    raw: str | None,
) -> tuple[int | None, str | None]:
    text = str(raw or "").strip()
    if not text:
        return None, None

    parsed = urlparse(
        text
        if "://" in text
        else f"http://_ignored{text if text.startswith('/') else '/' + text}"
    )
    parts = [part for part in (parsed.path or "").split("/") if part]
    if len(parts) < 4:
        return None, None
    if parts[0:3] != ["api", "public", "attachments"]:
        return None, None

    attachment_id = safe_positive_int(parts[3])
    if attachment_id is None:
        return None, None

    access_kind = parts[4].lower() if len(parts) > 4 else ""
    if access_kind not in {"access", "image"}:
        return None, None

    token_values = parse_qs(parsed.query or "").get("token") or []
    token = str(token_values[0]).strip() if token_values else None
    return attachment_id, token or None


__all__ = ["extract_public_attachment_reference"]
