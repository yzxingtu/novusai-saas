"""
Page context runtime payload limit helpers / 页面上下文运行期负载限制辅助函数
"""

from __future__ import annotations

import json
from typing import Any

from app.configs.service import ConfigService
from app.core.i18n import _
from app.exceptions import ValidationException

DEFAULT_PAGE_CONTEXT_MAX_BYTES = 8192


async def get_ui_runtime_payload_max_bytes(db: Any) -> int:
    """Resolve thin page_context runtime payload limit / 读取薄 page_context 运行期负载上限."""
    config_service = ConfigService(db)
    raw = await config_service.get_platform_config(
        "ai_page_context_max_bytes",
        default=DEFAULT_PAGE_CONTEXT_MAX_BYTES,
    )
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = DEFAULT_PAGE_CONTEXT_MAX_BYTES
    return max(value, 1)


async def validate_page_context_size(db: Any, page_context: Any) -> None:
    """Validate thin page_context runtime payload serialized size / 校验薄 page_context 运行期负载序列化大小."""
    if not page_context:
        return

    if hasattr(page_context, "model_dump"):
        payload = page_context.model_dump(exclude_none=True)
    elif isinstance(page_context, dict):
        payload = page_context
    else:
        return

    if not isinstance(payload, dict) or not payload:
        return

    serialized = json.dumps(payload, ensure_ascii=False, default=str)
    size = len(serialized.encode("utf-8"))
    limit = await get_ui_runtime_payload_max_bytes(db)
    if size <= limit:
        return

    raise ValidationException(
        message=_("agent_chat.error.page_context_too_large").format(
            current=size,
            limit=limit,
        ),
    )


__all__ = [
    "DEFAULT_PAGE_CONTEXT_MAX_BYTES",
    "get_ui_runtime_payload_max_bytes",
    "validate_page_context_size",
]
