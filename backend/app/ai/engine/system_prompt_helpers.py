"""Compatibility facade for system prompt helper seams."""

from __future__ import annotations

from typing import Any

from app.ai.types import ChatMessage
from app.models.ai.agent import Agent

from .system_prompt_capability_decisions import (
    resolve_capability_injection_decision as resolve_capability_injection_decision,
)
from .system_prompt_capability_decisions import (
    should_skip_capability_summary as should_skip_capability_summary,
)
from .system_prompt_capability_hints import (
    build_capability_reporting_hint as build_capability_reporting_hint,
)
from .system_prompt_capability_hints import (
    build_ordered_capability_hint as build_ordered_capability_hint,
)
from .system_prompt_capability_hints import (
    build_ordered_capability_hint_default as build_ordered_capability_hint_default,
)
from .system_prompt_capability_hints import (
    build_page_operations_hint as build_page_operations_hint,
)
from .system_prompt_capability_hints import (
    build_runtime_capability_hint as build_runtime_capability_hint,
)
from .system_prompt_capability_hints import (
    build_time_tools_hint as build_time_tools_hint,
)
from .system_prompt_capability_hints import (
    build_weather_tools_hint as build_weather_tools_hint,
)
from .system_prompt_capability_hints import (
    build_web_research_hint as build_web_research_hint,
)
from .system_prompt_intent_helpers import (
    deserialize_intent_plan as deserialize_intent_plan,
)
from .system_prompt_intent_helpers import (
    intent_completion_signals as intent_completion_signals,
)
from .system_prompt_intent_helpers import (
    intent_plan_gating_flags as intent_plan_gating_flags,
)
from .system_prompt_intent_helpers import (
    is_capability_reporting_query as is_capability_reporting_query,
)
from .system_prompt_rendering import build_system_message as build_system_message
from .system_prompt_runtime_summary import (
    build_research_continuation_hint as build_research_continuation_hint,
)
from .system_prompt_runtime_summary import (
    inject_runtime_summary as inject_runtime_summary,
)


def build_system_message_default(
    agent: Agent,
    input_variables: dict[str, Any] | None = None,
) -> ChatMessage:
    return build_system_message(
        agent=agent,
        input_variables=input_variables,
    )


__all__ = [
    "build_capability_reporting_hint",
    "build_ordered_capability_hint",
    "build_ordered_capability_hint_default",
    "build_page_operations_hint",
    "build_research_continuation_hint",
    "build_runtime_capability_hint",
    "build_system_message",
    "build_system_message_default",
    "build_time_tools_hint",
    "build_weather_tools_hint",
    "build_web_research_hint",
    "deserialize_intent_plan",
    "inject_runtime_summary",
    "intent_completion_signals",
    "intent_plan_gating_flags",
    "is_capability_reporting_query",
    "resolve_capability_injection_decision",
    "should_skip_capability_summary",
]
