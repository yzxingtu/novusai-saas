"""
System prompt and runtime summary bindings for BaseEngine.
"""

from __future__ import annotations

from typing import Any

from app.ai.prompt_contracts import render_prompt_contract
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage

from .intent_plan_accessors import (
    attach_intent_plan_to_input_variables as _attach_intent_plan_to_input_variables_impl,
)
from .system_prompt_helpers import (
    build_capability_reporting_hint as _build_capability_reporting_hint_impl,
)
from .system_prompt_helpers import (
    build_ordered_capability_hint_default as _build_ordered_capability_hint_default_impl,
)
from .system_prompt_helpers import (
    build_page_operations_hint as _build_page_operations_hint_impl,
)
from .system_prompt_helpers import (
    build_research_continuation_hint as _build_research_continuation_hint_impl,
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
    build_weather_tools_hint as _build_weather_tools_hint_impl,
)
from .system_prompt_helpers import (
    build_web_research_hint as _build_web_research_hint_impl,
)
from .system_prompt_helpers import (
    deserialize_intent_plan as _deserialize_intent_plan_impl,
)
from .system_prompt_helpers import (
    inject_runtime_summary as _inject_runtime_summary_impl,
)
from .system_prompt_helpers import (
    intent_completion_signals as _intent_completion_signals_impl,
)
from .system_prompt_helpers import (
    intent_plan_gating_flags as _intent_plan_gating_flags_impl,
)
from .system_prompt_helpers import (
    is_capability_reporting_query as _is_capability_reporting_query_impl,
)
from .types import ExecutionBudget, IntentPlan, ResearchContinuationContext


class BasePromptSystemSupportMixin:
    """Binds system prompt and runtime summary helpers onto BaseEngine."""

    _build_system_message = staticmethod(_build_system_message_default_impl)

    @staticmethod
    def _inject_runtime_summary(
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        _input_variables: dict[str, Any] | None = None,
        continuation_context: ResearchContinuationContext | None = None,
        runtime_capability_summary: dict[str, Any] | None = None,
        ordered_requested_families: list[str] | None = None,
        skip_capability_summary: bool = False,
        intent_plan: list[IntentPlan] | None = None,
        execution_path: str | None = None,
        execution_budget: ExecutionBudget | None = None,
        include_knowledge_base_hint: bool = True,
        include_page_context_hint: bool = True,
        include_memory_hint: bool = True,
    ) -> bool:
        return _inject_runtime_summary_impl(
            messages=messages,
            tools=tools,
            continuation_context=continuation_context,
            runtime_capability_summary=runtime_capability_summary,
            ordered_requested_families=ordered_requested_families,
            skip_capability_summary=skip_capability_summary,
            intent_plan=intent_plan,
            execution_path=execution_path,
            execution_budget=execution_budget,
            include_knowledge_base_hint=include_knowledge_base_hint,
            include_page_context_hint=include_page_context_hint,
            include_memory_hint=include_memory_hint,
            render_contract=render_prompt_contract,
        )

    @staticmethod
    def _build_page_operations_hint(
        input_variables: dict[str, Any] | None,
        tools: list[ToolDefinition] | None = None,
    ) -> str:
        return _build_page_operations_hint_impl(
            input_variables=input_variables,
            tools=tools,
            render_contract=render_prompt_contract,
        )

    _deserialize_intent_plan = staticmethod(_deserialize_intent_plan_impl)
    _intent_plan_gating_flags = staticmethod(_intent_plan_gating_flags_impl)
    _is_capability_reporting_query = staticmethod(_is_capability_reporting_query_impl)
    _intent_completion_signals = staticmethod(_intent_completion_signals_impl)
    _build_web_research_hint = staticmethod(_build_web_research_hint_impl)
    _build_weather_tools_hint = staticmethod(_build_weather_tools_hint_impl)
    _build_time_tools_hint = staticmethod(_build_time_tools_hint_impl)
    _build_capability_reporting_hint = staticmethod(
        _build_capability_reporting_hint_impl
    )
    _build_runtime_capability_hint = staticmethod(
        _build_runtime_capability_hint_impl
    )
    _build_ordered_capability_hint = staticmethod(
        _build_ordered_capability_hint_default_impl
    )
    _build_research_continuation_hint = staticmethod(
        _build_research_continuation_hint_impl
    )
    _attach_intent_plan_to_input_variables = staticmethod(
        _attach_intent_plan_to_input_variables_impl
    )


__all__ = ["BasePromptSystemSupportMixin"]
