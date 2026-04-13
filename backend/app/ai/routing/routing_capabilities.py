"""
Capability checks and attachment detection for routing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.ai.types import ChatMessage
    from app.models.ai.model import AIModel


def model_satisfies_requirements(
    model: AIModel | None,
    *,
    needs_vision: bool = False,
    needs_audio: bool = False,
    needs_video: bool = False,
    needs_fc: bool = False,
    min_context_window: int | None = None,
) -> bool:
    """Check whether a model satisfies the required capability set. / 检查模型是否满足所需能力组合。"""
    if model is None:
        return False
    if needs_vision and not bool(getattr(model, "supports_vision", False)):
        return False
    if needs_audio and not bool(getattr(model, "supports_audio", False)):
        return False
    if needs_video and not bool(getattr(model, "supports_video", False)):
        return False
    if needs_fc and not bool(getattr(model, "supports_function_calling", False)):
        return False
    if min_context_window is not None:
        context_window = int(getattr(model, "context_window", 0) or 0)
        if context_window < min_context_window:
            return False
    return True


def detect_image_attachments(
    request_attachments: list[dict[str, Any]] | None,
    messages: list[ChatMessage],
) -> bool:
    """
    Detect if request contains image attachments (request-level + message-level).
    检测请求中是否包含图片附件（request 级 + message 级）。
    """
    if request_attachments:
        for att in request_attachments:
            if isinstance(att, dict) and att.get("type") == "image":
                return True

    for msg in messages:
        if msg.attachments:
            for att in msg.attachments:
                if isinstance(att, dict) and att.get("type") == "image":
                    return True

    return False


def detect_any_attachments(
    request_attachments: list[dict[str, Any]] | None,
    messages: list[ChatMessage],
) -> bool:
    """
    Detect whether the request contains any attachment, including message-level files.
    检测请求是否包含任意附件，包括消息级文件附件。
    """
    if request_attachments:
        return True
    return any(bool(getattr(msg, "attachments", None)) for msg in messages)


def detect_audio_video_attachments(
    request_attachments: list[dict[str, Any]] | None,
    messages: list[ChatMessage],
) -> tuple[bool, bool]:
    """
    Detect if request contains audio/video attachments (request-level + message-level).
    检测请求中是否包含音频/视频附件（request 级 + message 级）。

    Returns:
        (has_audio, has_video)
    """
    has_audio = False
    has_video = False

    def check_att(att: dict[str, Any]) -> None:
        nonlocal has_audio, has_video
        t = att.get("type") if isinstance(att, dict) else None
        if t == "audio":
            has_audio = True
        elif t == "video":
            has_video = True

    if request_attachments:
        for att in request_attachments:
            check_att(att)
    for msg in messages:
        if msg.attachments:
            for att in msg.attachments:
                check_att(att)

    return has_audio, has_video


__all__ = [
    "detect_any_attachments",
    "detect_audio_video_attachments",
    "detect_image_attachments",
    "model_satisfies_requirements",
]
