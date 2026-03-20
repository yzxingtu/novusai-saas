"""
Page context runtime limit helpers / 页面上下文运行期限制辅助函数
"""

from __future__ import annotations

import json
from typing import Any

from app.configs.service import ConfigService
from app.core.i18n import _
from app.exceptions import ValidationException

DEFAULT_PAGE_CONTEXT_MAX_BYTES = 8192


async def get_page_context_max_bytes(db: Any) -> int:
    """Resolve page_context.page_data hard limit from platform config / 从平台配置读取 page_context.page_data 硬限制."""
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
    """Validate page_context.page_data serialized size at runtime / 在运行期校验 page_context.page_data 序列化大小."""
    if not page_context:
        return

    if hasattr(page_context, "model_dump"):
        payload = page_context.model_dump(exclude_none=True)
    elif isinstance(page_context, dict):
        payload = page_context
    else:
        return

    page_data = payload.get("page_data")
    if not isinstance(page_data, dict):
        return

    serialized = json.dumps(page_data, ensure_ascii=False, default=str)
    size = len(serialized.encode("utf-8"))
    limit = await get_page_context_max_bytes(db)
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
    "get_page_context_max_bytes",
    "validate_page_context_size",
]
