"""Tool definitions for page-runtime ui_* tools."""

from __future__ import annotations

from app.ai.tools.types import ToolDefinition


def build_page_runtime_tool_definitions() -> list[ToolDefinition]:
    """Return no live page-runtime tools.

    The page-awareness/runtime UI bridge has been retired from AI dialogue.
    Keep this import-compatible seam so legacy modules/tests can still import
    the function without re-exposing ui_* tools to the model.
    """
    return []
