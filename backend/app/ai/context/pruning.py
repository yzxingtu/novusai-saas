"""
Transient prompt pruning / Prompt 临时裁剪

Prunes older low-value tool payloads from the in-memory prompt assembly only.
只对内存中的 prompt 组装结果做裁剪，不修改数据库原始历史。
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass

from app.ai.types import ChatMessage

_PRUNED_TOOL_PLACEHOLDER = "[Older tool result omitted from prompt]"


@dataclass
class PruneStats:
    """Transient pruning diagnostics / 临时裁剪诊断信息"""

    mode: str = "off"
    enabled: bool = False
    bytes_before: int = 0
    bytes_after: int = 0
    pruned_message_count: int = 0
    pruned_tool_message_count: int = 0
    pruned_tool_call_count: int = 0

    def to_dict(self) -> dict[str, int | bool | str]:
        return {
            "mode": self.mode,
            "enabled": self.enabled,
            "bytes_before": self.bytes_before,
            "bytes_after": self.bytes_after,
            "pruned_message_count": self.pruned_message_count,
            "pruned_tool_message_count": self.pruned_tool_message_count,
            "pruned_tool_call_count": self.pruned_tool_call_count,
        }


class TransientPruner:
    """
    Prompt-only tool-result pruner / 仅 prompt 层的工具结果裁剪器。

    Rules:
    - Never mutates the source message list / 不修改源消息列表
    - Never touches user messages / 不碰用户消息
    - Protects the most recent assistant turns / 保护最近 assistant 轮次
    - Skips unresolved confirmation/consent rounds / 跳过未决确认/授权轮次
    """

    def __init__(
        self,
        *,
        keep_last_assistants: int = 3,
        min_prunable_tool_chars: int = 4000,
    ) -> None:
        self.keep_last_assistants = max(1, keep_last_assistants)
        self.min_prunable_tool_chars = max(256, min_prunable_tool_chars)

    def prune(self, messages: list[ChatMessage]) -> tuple[list[ChatMessage], PruneStats]:
        cloned = [copy.deepcopy(message) for message in messages]
        stats = PruneStats(
            mode="transient_tool_result_pruning",
            enabled=True,
            bytes_before=sum(self._message_prompt_bytes(message) for message in cloned),
        )

        cutoff_index = self._assistant_protection_cutoff(cloned)
        if cutoff_index is None:
            stats.bytes_after = stats.bytes_before
            return cloned, stats

        for idx, message in enumerate(cloned):
            if idx >= cutoff_index:
                continue

            if message.role == "tool":
                if self._has_unresolved_tool_state(message):
                    continue
                if len(message.content or "") < self.min_prunable_tool_chars:
                    continue
                message.content = _PRUNED_TOOL_PLACEHOLDER
                stats.pruned_message_count += 1
                stats.pruned_tool_message_count += 1
                continue

            if message.role == "assistant" and message.tool_calls:
                if self._assistant_has_unresolved_tool_state(message):
                    continue
                pruned_call_count = self._prune_tool_calls(message.tool_calls)
                if pruned_call_count > 0:
                    stats.pruned_message_count += 1
                    stats.pruned_tool_call_count += pruned_call_count

        stats.bytes_after = sum(self._message_prompt_bytes(message) for message in cloned)
        return cloned, stats

    def _assistant_protection_cutoff(self, messages: list[ChatMessage]) -> int | None:
        assistant_indexes = [
            idx
            for idx, message in enumerate(messages)
            if message.role == "assistant"
        ]
        if len(assistant_indexes) <= self.keep_last_assistants:
            return None
        return assistant_indexes[-self.keep_last_assistants]

    @staticmethod
    def _has_unresolved_tool_state(message: ChatMessage) -> bool:
        content = (message.content or "").strip()
        if not content or not content.startswith("{"):
            return False
        try:
            parsed = json.loads(content)
        except (TypeError, ValueError, json.JSONDecodeError):
            return False
        if not isinstance(parsed, dict):
            return False
        return bool(
            parsed.get("requires_confirmation")
            or parsed.get("consent_required")
            or parsed.get("action") == "tool_consent"
        )

    @staticmethod
    def _assistant_has_unresolved_tool_state(message: ChatMessage) -> bool:
        for tool_call in message.tool_calls or []:
            if tool_call.get("pending_confirmation") or tool_call.get("pending_consent"):
                return True
        return False

    def _prune_tool_calls(self, tool_calls: list[dict]) -> int:
        changed_count = 0
        for tool_call in tool_calls:
            call_changed = False

            summary_payload = tool_call.get("summary_payload")
            if (
                isinstance(summary_payload, dict)
                and len(json.dumps(summary_payload, ensure_ascii=False)) >= 1000
            ):
                tool_call["summary_payload"] = {
                    "_pruned": "Older tool summary payload omitted"
                }
                call_changed = True

            function_data = tool_call.get("function")
            if isinstance(function_data, dict):
                raw_args = function_data.get("arguments")
                if isinstance(raw_args, str) and len(raw_args) > 1000:
                    function_data["arguments"] = raw_args[:500] + "...[truncated]"
                    call_changed = True

            if call_changed:
                changed_count += 1
        return changed_count

    @staticmethod
    def _message_prompt_bytes(message: ChatMessage) -> int:
        size = len(message.content or "")
        for tool_call in message.tool_calls or []:
            function_data = tool_call.get("function")
            if isinstance(function_data, dict):
                raw_args = function_data.get("arguments")
                if isinstance(raw_args, str):
                    size += len(raw_args)
            summary_payload = tool_call.get("summary_payload")
            if isinstance(summary_payload, dict):
                size += len(json.dumps(summary_payload, ensure_ascii=False))
        return size
