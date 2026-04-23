"""Model request policy helpers shared by sync and stream execution."""

from __future__ import annotations

from typing import Any

FAST_PATH_REASONING_EFFORT = "low"
_PAGE_TOOL_PREFIX = "ui_"


def _extract_tool_name(tool: Any) -> str:
    if isinstance(tool, str):
        return str(tool).strip()
    if isinstance(tool, dict):
        function_block = tool.get("function") or {}
        return str(function_block.get("name") or tool.get("name") or "").strip()
    return str(getattr(tool, "name", "") or "").strip()


def _is_page_ui_tool_turn(tools: list[Any] | None) -> bool:
    if not tools:
        return False
    tool_names = [_extract_tool_name(tool) for tool in tools]
    normalized_names = [name for name in tool_names if name]
    return bool(normalized_names) and all(
        name.startswith(_PAGE_TOOL_PREFIX) for name in normalized_names
    )


def build_model_request_overrides(
    *,
    execution_path: str | None,
    tools: list[Any] | None,
) -> dict[str, Any]:
    """Apply lightweight model overrides for fast, text-only rounds."""

    normalized_path = str(execution_path or "").strip().lower()
    if _is_page_ui_tool_turn(tools):
        return {
            "_runtime_reasoning_effort_override": FAST_PATH_REASONING_EFFORT,
        }
    if normalized_path != "fast":
        return {}
    if tools:
        return {}
    return {
        "_runtime_reasoning_effort_override": FAST_PATH_REASONING_EFFORT,
    }


__all__ = ["FAST_PATH_REASONING_EFFORT", "build_model_request_overrides"]
