"""Conversation export formatting helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import Mock

from app.core.i18n import _
from app.enums.agent import MessageRoleEnum
from app.models.ai.agent_conversation import AgentConversation


def _format_dt(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _msg_get(message: Any, key: str, default: Any = None) -> Any:
    if isinstance(message, dict):
        return message.get(key, default)
    if hasattr(message, "__dict__") and key in vars(message):
        return vars(message).get(key, default)
    value = getattr(message, key, default)
    return default if isinstance(value, Mock) else value


def _related_attr(message: Any, relation: str, key: str) -> Any:
    if isinstance(message, dict):
        return None
    relation_obj = _msg_get(message, relation)
    if relation_obj is None:
        return None
    if hasattr(relation_obj, "__dict__") and key in vars(relation_obj):
        return vars(relation_obj).get(key)
    value = getattr(relation_obj, key, None)
    return None if isinstance(value, Mock) else value


class ConversationExportService:
    """Formats persisted conversations into JSON or Markdown exports."""

    @staticmethod
    def to_json(
        conversation: AgentConversation,
        messages: list[Any],
    ) -> str:
        data = {
            "id": conversation.id,
            "title": conversation.title,
            "status": conversation.status,
            "token_count": conversation.token_count,
            "created_at": _format_dt(conversation.created_at),
            "messages": [
                {
                    "role": _msg_get(msg, "role"),
                    "content": _msg_get(msg, "content"),
                    "token_count": _msg_get(msg, "token_count"),
                    "tool_calls": _msg_get(msg, "tool_calls"),
                    "tool_call_id": _msg_get(msg, "tool_call_id"),
                    "agent_id": _msg_get(msg, "agent_id"),
                    "agent_name": _msg_get(
                        msg,
                        "agent_name",
                        _related_attr(msg, "agent", "name"),
                    ),
                    "agent_avatar": _msg_get(
                        msg,
                        "agent_avatar",
                        _related_attr(msg, "agent", "avatar"),
                    ),
                    "created_at": _msg_get(
                        msg,
                        "created_at",
                        _format_dt(_msg_get(msg, "created_at")),
                    ),
                    "metadata": _msg_get(
                        msg,
                        "metadata",
                        _msg_get(msg, "metadata_"),
                    ),
                }
                for msg in messages
            ],
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    @staticmethod
    def to_markdown(
        conversation: AgentConversation,
        messages: list[Any],
    ) -> str:
        role_labels = {
            MessageRoleEnum.SYSTEM.value: _("conversation.export.role.system"),
            MessageRoleEnum.USER.value: _("conversation.export.role.user"),
            MessageRoleEnum.ASSISTANT.value: _("conversation.export.role.assistant"),
            MessageRoleEnum.TOOL.value: _("conversation.export.role.tool"),
        }

        title = conversation.title or f"Conversation #{conversation.id}"
        lines = [f"# {title}", ""]

        for msg in messages:
            role = _msg_get(msg, "role", "")
            label = role_labels.get(role, role)
            agent_name = _msg_get(
                msg,
                "agent_name",
                _related_attr(msg, "agent", "name"),
            )
            if agent_name:
                lines.append(f"## {label} ({agent_name})")
            elif _msg_get(msg, "agent_id"):
                lines.append(f"## {label} (#{_msg_get(msg, 'agent_id')})")
            else:
                lines.append(f"## {label}")
            lines.append("")
            lines.append(_msg_get(msg, "content") or "")
            lines.append("")

            tool_calls = _msg_get(msg, "tool_calls")
            if tool_calls:
                lines.append("**Tool Calls:**")
                lines.append(
                    f"```json\n{json.dumps(tool_calls, indent=2, ensure_ascii=False)}\n```"
                )
                lines.append("")

            metadata = _msg_get(msg, "metadata", _msg_get(msg, "metadata_"))
            attachments = (
                metadata.get("attachments") if isinstance(metadata, dict) else None
            )
            if isinstance(attachments, list) and attachments:
                lines.append("**Attachments:**")
                for item in attachments:
                    if not isinstance(item, dict):
                        continue
                    att_type = str(item.get("type") or "file")
                    name = str(item.get("name") or item.get("url") or "-")
                    attachment_id = item.get("attachment_id")
                    url = str(item.get("url") or "").strip()
                    suffix = f" (#{attachment_id})" if attachment_id else ""
                    if url:
                        lines.append(f"- `{att_type}` {name}{suffix} `{url}`")
                    else:
                        lines.append(f"- `{att_type}` {name}{suffix}")
                lines.append("")

        return "\n".join(lines)


__all__ = ["ConversationExportService"]
