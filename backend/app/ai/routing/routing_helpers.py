"""
Routing helper utilities.
"""

from __future__ import annotations

from app.enums.ai import ModelTierEnum


def build_multimodal_reason(
    *,
    has_image: bool,
    has_audio: bool,
    has_video: bool,
    suffix: str,
) -> str:
    parts: list[str] = []
    if has_image:
        parts.append("vision")
    if has_audio:
        parts.append("audio")
    if has_video:
        parts.append("video")
    if not parts:
        parts.append("multimodal")
    return ":".join(parts + [suffix])


def get_multimodal_error_key(
    *,
    has_image: bool,
    has_audio: bool,
    has_video: bool,
) -> str:
    if has_image and not has_audio and not has_video:
        return "agent_chat.error.no_vision_model_available"
    if has_audio and has_video and not has_image:
        return "agent_chat.error.no_audio_video_model_available"
    if has_audio and not has_image and not has_video:
        return "agent_chat.error.no_audio_model_available"
    if has_video and not has_image and not has_audio:
        return "agent_chat.error.no_video_model_available"
    return "agent_chat.error.no_multimodal_model_available"


def filter_tiers_by_max(tiers: list[str], max_tier: str) -> list[str]:
    """
    Filter by max_tier, keeping only tiers not exceeding max_tier level.
    按 max_tier 过滤，只保留不超过 max_tier 级别的 tier。
    """
    order = [
        ModelTierEnum.FAST.value,
        ModelTierEnum.STANDARD.value,
        ModelTierEnum.PREMIUM.value,
    ]
    try:
        max_index = order.index(max_tier)
    except ValueError:
        return tiers
    return [t for t in tiers if t in order and order.index(t) <= max_index]


__all__ = [
    "build_multimodal_reason",
    "filter_tiers_by_max",
    "get_multimodal_error_key",
]
