"""Responses API input conversion helpers for OpenAI-compatible adapters."""

from __future__ import annotations

from typing import Any, Protocol

from app.ai.types import ChatMessage


class ResponsesInputAdapterProtocol(Protocol):
    async def _resolve_image_url_for_llm(
        self,
        att_url: str,
        att_mime: str,
        *,
        attachment_id: object = None,
    ) -> str | None: ...


def _as_non_empty_str(value: Any) -> str:
    return str(value or "").strip()


def _is_responses_item_id(value: str) -> bool:
    return value.startswith("fc_")


def _is_responses_call_id(value: str) -> bool:
    return value.startswith("call_")


def _synthesize_call_id(
    *,
    assistant_index: int,
    tool_index: int,
    tool_name: str,
) -> str:
    safe_name = (
        "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in tool_name) or "tool"
    )
    return f"call_{assistant_index + 1}_{tool_index + 1}_{safe_name}"


def _peek_following_tool_call_ids(
    messages: list[ChatMessage],
    assistant_index: int,
) -> list[str]:
    ids: list[str] = []
    for msg in messages[assistant_index + 1 :]:
        if msg.role != "tool":
            break
        tool_call_id = _as_non_empty_str(msg.tool_call_id)
        if tool_call_id:
            ids.append(tool_call_id)
    return ids


def _resolve_function_call_identity(
    *,
    assistant_index: int,
    tool_call: dict[str, Any],
    tool_index: int,
    following_tool_call_ids: list[str],
) -> tuple[str, str | None]:
    function = tool_call.get("function") or {}
    tool_name = _as_non_empty_str(function.get("name"))
    item_id = _as_non_empty_str(tool_call.get("id"))
    explicit_call_id = _as_non_empty_str(
        tool_call.get("call_id") or tool_call.get("tool_call_id")
    )
    if explicit_call_id:
        return explicit_call_id, item_id if _is_responses_item_id(item_id) else None

    if item_id and not _is_responses_item_id(item_id):
        return item_id, None

    candidate_tool_call_id = (
        following_tool_call_ids[tool_index]
        if tool_index < len(following_tool_call_ids)
        else ""
    )
    if _is_responses_call_id(candidate_tool_call_id):
        return candidate_tool_call_id, item_id if _is_responses_item_id(
            item_id
        ) else None

    return (
        _synthesize_call_id(
            assistant_index=assistant_index,
            tool_index=tool_index,
            tool_name=tool_name,
        ),
        item_id if _is_responses_item_id(item_id) else None,
    )


async def build_responses_message_content(
    *,
    adapter: ResponsesInputAdapterProtocol,
    msg: ChatMessage,
    supports_vision: bool = True,
    supports_audio: bool = False,
    supports_video: bool = False,
) -> str | list[dict[str, Any]]:
    if msg.role != "user" or not msg.attachments:
        return msg.content or ""

    parts: list[dict[str, Any]] = []
    if msg.content:
        parts.append({"type": "input_text", "text": msg.content})

    for att in msg.attachments:
        att_type = str(att.get("type") or "").lower()
        url = str(att.get("url") or "").strip()
        name = att.get("name") or att.get("filename") or "file"
        att_mime = str(att.get("mime_type") or "")
        attachment_id = att.get("attachment_id")

        if att_type == "image":
            if supports_vision and url:
                resolved = await adapter._resolve_image_url_for_llm(
                    url,
                    att_mime,
                    attachment_id=attachment_id,
                )
                if resolved:
                    parts.append(
                        {
                            "type": "input_image",
                            "image_url": resolved,
                            "detail": "auto",
                        }
                    )
                else:
                    parts.append(
                        {
                            "type": "input_text",
                            "text": (
                                f"[Image: {name or 'uploaded image'} "
                                "(could not load for model)]"
                            ),
                        }
                    )
            else:
                parts.append({"type": "input_text", "text": f"[Image: {name}]"})
            continue

        if att_type == "file":
            if url:
                parts.append(
                    {
                        "type": "input_file",
                        "file_url": url,
                        "filename": str(name),
                    }
                )
            else:
                parts.append({"type": "input_text", "text": f"[File: {name}]"})
            continue

        if att_type == "audio":
            if supports_audio and url:
                parts.append(
                    {
                        "type": "input_file",
                        "file_url": url,
                        "filename": str(name),
                    }
                )
            else:
                parts.append({"type": "input_text", "text": f"[Audio: {name}]"})
            continue

        if att_type == "video":
            if supports_video and url:
                parts.append(
                    {
                        "type": "input_file",
                        "file_url": url,
                        "filename": str(name),
                    }
                )
            else:
                parts.append({"type": "input_text", "text": f"[Video: {name}]"})
            continue

        parts.append({"type": "input_text", "text": f"[Attachment: {name}]"})

    return parts or (msg.content or "")


async def convert_messages_to_responses_input(
    *,
    adapter: ResponsesInputAdapterProtocol,
    messages: list[ChatMessage],
    supports_vision: bool = True,
    supports_audio: bool = False,
    supports_video: bool = False,
) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    pending_call_ids: list[dict[str, str | None]] = []

    def pop_pending_tool_call(tool_call_id: str) -> str | None:
        if not pending_call_ids:
            return None
        if not tool_call_id:
            return str(pending_call_ids.pop(0)["call_id"] or "")
        for index, pending in enumerate(pending_call_ids):
            if tool_call_id in {pending.get("call_id"), pending.get("item_id")}:
                pending_call_ids.pop(index)
                return str(pending.get("call_id") or "")
        if _is_responses_call_id(tool_call_id):
            return tool_call_id
        return None

    for message_index, msg in enumerate(messages):
        if msg.role == "tool":
            call_id = pop_pending_tool_call(_as_non_empty_str(msg.tool_call_id))
            if not call_id:
                continue
            converted.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": msg.content or "",
                }
            )
            continue

        if msg.role == "assistant" and msg.tool_calls:
            following_tool_call_ids = _peek_following_tool_call_ids(
                messages,
                message_index,
            )
            for tool_index, tool_call in enumerate(msg.tool_calls):
                function = tool_call.get("function") or {}
                call_id, item_id = _resolve_function_call_identity(
                    assistant_index=message_index,
                    tool_call=tool_call,
                    tool_index=tool_index,
                    following_tool_call_ids=following_tool_call_ids,
                )
                payload = {
                    "type": "function_call",
                    "call_id": call_id,
                    "name": function.get("name", ""),
                    "arguments": function.get("arguments", "{}") or "{}",
                    "status": "completed",
                }
                if item_id:
                    payload["id"] = item_id
                converted.append(payload)
                pending_call_ids.append({"call_id": call_id, "item_id": item_id})
            if not (msg.content or "").strip():
                continue

        content = await build_responses_message_content(
            adapter=adapter,
            msg=msg,
            supports_vision=supports_vision,
            supports_audio=supports_audio,
            supports_video=supports_video,
        )
        converted.append(
            {
                "type": "message",
                "role": msg.role,
                "content": content,
            }
        )

    return converted


__all__ = [
    "build_responses_message_content",
    "convert_messages_to_responses_input",
]
