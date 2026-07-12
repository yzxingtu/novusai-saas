"""
System prompt and runtime summary bindings for BaseEngine.
"""

from __future__ import annotations

from typing import Any

from app.ai.prompt_contracts import render_prompt_contract
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage

from .system_prompt_helpers import (
    build_ordered_capability_hint_default as _build_ordered_capability_hint_default_impl,
)
from .system_prompt_helpers import (
    build_runtime_capability_hint as _build_runtime_capability_hint_impl,
)
from .system_prompt_helpers import (
    build_system_message_default as _build_system_message_default_impl,
)
from .system_prompt_helpers import (
    build_time_tools_hint as _build_time_tools_hint_impl,
)
from .system_prompt_helpers import (
    inject_runtime_summary as _inject_runtime_summary_impl,
)
from .types import IntentPlan


class BasePromptSystemSupportMixin:
    """Binds system prompt and runtime summary helpers onto BaseEngine."""

    _build_system_message = staticmethod(_build_system_message_default_impl)

    @staticmethod
    def _inject_runtime_summary(
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        runtime_capability_summary: dict[str, Any] | None = None,
        ordered_requested_families: list[str] | None = None,
        skip_capability_summary: bool = False,
        intent_plan: list[IntentPlan] | None = None,
        execution_path: str | None = None,
    ) -> bool:
        return _inject_runtime_summary_impl(
            messages=messages,
            tools=tools,
            runtime_capability_summary=runtime_capability_summary,
            ordered_requested_families=ordered_requested_families,
            skip_capability_summary=skip_capability_summary,
            intent_plan=intent_plan,
            execution_path=execution_path,
            render_contract=render_prompt_contract,
        )

    _build_time_tools_hint = staticmethod(_build_time_tools_hint_impl)

    _build_runtime_capability_hint = staticmethod(_build_runtime_capability_hint_impl)
    _build_ordered_capability_hint = staticmethod(
        _build_ordered_capability_hint_default_impl
    )

    @staticmethod
    def _attach_intent_plan_to_input_variables(
        input_variables: dict[str, Any] | None,
        intent_plan: list[Any] | None,
    ) -> None:
        """No-op: intent planner removed (#57)."""


__all__ = ["BasePromptSystemSupportMixin"]
