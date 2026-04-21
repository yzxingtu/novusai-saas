"""
Knowledge base read-model projection helpers.
"""

from __future__ import annotations

from typing import Any

from app.models.ai.knowledge_base import KnowledgeBase

_RETIRED_MULTIMODAL_MODEL_KEYS = (
    "audio_model_id",
    "audio_model_name",
    "video_model_id",
    "video_model_name",
)


def _safe_model_name(kb: KnowledgeBase, attr_name: str) -> str | None:
    try:
        model_obj = getattr(kb, attr_name, None)
    except AttributeError:
        return None
    if model_obj is None:
        return None
    return getattr(model_obj, "name", None)


def build_kb_detail(kb: KnowledgeBase) -> dict[str, Any]:
    result = kb.to_dict()
    for key in _RETIRED_MULTIMODAL_MODEL_KEYS:
        result.pop(key, None)
    result["embedding_model_name"] = _safe_model_name(kb, "embedding_model")
    result["vision_model_name"] = _safe_model_name(kb, "vision_model")
    return result


__all__ = ["build_kb_detail"]
