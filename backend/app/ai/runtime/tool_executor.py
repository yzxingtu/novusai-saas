"""
Tool round execution/runtime guards.
工具轮执行/运行时校验。
"""

from __future__ import annotations

from typing import Any

from app.ai.runtime.types import TurnRecord


class ToolExecutor:
    """
    Minimal runtime guard for tool-round contract checks.
    工具轮契约校验（第一版最小实现）。
    """

    REQUIRED_EMPTY_FAILURE = "required_tool_round_empty_no_tool_calls"

    @staticmethod
    def has_tool_calls(tool_calls: list[dict[str, Any]] | None) -> bool:
        if not tool_calls:
            return False
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            function_block = tool_call.get("function") or {}
            name = str(
                function_block.get("name") or tool_call.get("name") or ""
            ).strip()
            if name:
                return True
        return False

    @staticmethod
    def has_visible_output(text: str | None) -> bool:
        return bool((text or "").strip())

    @staticmethod
    def has_reasoning_output(text: str | None) -> bool:
        return bool((text or "").strip())

    @classmethod
    def has_meaningful_chunk(
        cls,
        *,
        delta: str | None,
        reasoning_delta: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> bool:
        return (
            cls.has_visible_output(delta)
            or cls.has_reasoning_output(reasoning_delta)
            or cls.has_tool_calls(tool_calls)
        )

    @classmethod
    def required_empty_violation(
        cls,
        *,
        tool_choice: str | None,
        output_text: str | None,
        tool_calls: list[dict[str, Any]] | None,
    ) -> bool:
        return (
            str(tool_choice or "").strip().lower() == "required"
            and not cls.has_visible_output(output_text)
            and not cls.has_tool_calls(tool_calls)
        )

    @classmethod
    def enforce_required_contract(
        cls,
        *,
        tool_choice: str | None,
        output_text: str | None,
        tool_calls: list[dict[str, Any]] | None,
        turn_record: TurnRecord | None = None,
    ) -> None:
        if not cls.required_empty_violation(
            tool_choice=tool_choice,
            output_text=output_text,
            tool_calls=tool_calls,
        ):
            return
        if turn_record is not None:
            turn_record.turn_outcome = "tool_round_failed"
            turn_record.termination_reason = "tool_round_empty"
            turn_record.metadata["failure_reason"] = cls.REQUIRED_EMPTY_FAILURE
        raise RuntimeError(cls.REQUIRED_EMPTY_FAILURE)


__all__ = ["ToolExecutor"]
