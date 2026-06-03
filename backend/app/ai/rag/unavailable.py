"""
Optional RAG availability helpers / 可选 RAG 可用性辅助。
"""

from __future__ import annotations

from app.core.i18n import _
from app.exceptions import BusinessException


def rag_unavailable_message_candidates() -> set[str]:
    """中文: 返回可降级 RAG 依赖缺失错误；EN: Return RAG dependency errors that may degrade."""
    return {
        str(_("ai.no_api_key") or "").strip(),
        str(_("ai.api_key_unavailable") or "").strip(),
        str(_("ai.error.embedding_model_not_configured") or "").strip(),
        str(_("ai.error.embedding_provider_not_found") or "").strip(),
    }


def is_rag_unavailable_error(exc: BusinessException) -> bool:
    """中文: 判断异常是否代表可选 RAG 依赖不可用；EN: Detect optional RAG dependency outages."""
    message = str(getattr(exc, "message", None) or exc).strip()
    return bool(message and message in rag_unavailable_message_candidates())


__all__ = ["is_rag_unavailable_error", "rag_unavailable_message_candidates"]
