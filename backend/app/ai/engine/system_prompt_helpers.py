"""System prompt and runtime summary helpers extracted from BaseEngine."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

from jinja2 import (
    BaseLoader,
    ChainableUndefined,
    Environment,
    TemplateSyntaxError,
    UndefinedError,
)

from app.ai.context.orchestrator import ContextPipelineOrchestrator
from app.ai.prompt_contracts import render_prompt_contract
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage
from app.core.config import settings
from app.core.i18n import _
from app.core.logging import LogManager
from app.models.ai.agent import Agent

from .types import (
    ExecutionBudget,
    IntentPlan,
    ResearchContinuationContext,
)

logger = LogManager.get_logger("ai.engine")

_CAPABILITY_REPORTING_QUERY_TERMS = (
    "这轮有哪些能力",
    "当前能力",
    "本轮能力",
    "你有哪些能力",
    "你能做什么",
    "可以做什么",
    "能力有哪些",
    "available capabilities",
    "current capabilities",
    "capabilities this turn",
    "what can you do this turn",
    "what can you do",
)

_jinja_env = Environment(
    loader=BaseLoader(),
    keep_trailing_newline=True,
    undefined=ChainableUndefined,
)


def build_system_message(
    *,
    agent: Agent,
    input_variables: dict[str, Any] | None = None,
) -> ChatMessage:
    """Render system prompt with built-in variables and identity declaration."""
    prompt = agent.system_prompt or ""
    agent_name = agent.name or ""

    if not prompt:
        return ChatMessage(role="system", content=prompt)

    if agent_name:
        identity = _("agent.identity_declaration").format(agent_name=agent_name)
        prompt = f"{identity}\n\n{prompt}"

    now = datetime.now(settings.tz)
    variables: dict[str, Any] = {
        "current_date": now.strftime("%Y-%m-%d"),
        "current_time": now.strftime("%H:%M:%S"),
        "current_timezone": settings.TIMEZONE,
        "agent_name": agent_name,
    }
    if input_variables:
        variables.update(input_variables)

    try:
        template = _jinja_env.from_string(prompt)
        prompt = template.render(**variables)
    except TemplateSyntaxError as exc:
        logger.warning(
            "Template syntax error: agent_id={} error={}",
            agent.id,
            str(exc),
        )
    except UndefinedError as exc:
        logger.warning(
            "Template undefined variable: agent_id={} error={}",
            agent.id,
            str(exc),
        )
    except Exception as exc:
        logger.warning(
            "Template render error: agent_id={} error={}",
            agent.id,
            str(exc),
        )

    return ChatMessage(role="system", content=prompt)


def build_system_message_default(
    agent: Agent,
    input_variables: dict[str, Any] | None = None,
) -> ChatMessage:
    return build_system_message(
        agent=agent,
        input_variables=input_variables,
    )


def inject_runtime_summary(
    *,
    messages: list[ChatMessage],
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
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
    render_contract: Callable[..., str] = render_prompt_contract,
) -> bool:
    """Inject a one-shot runtime summary into the first system message."""
    _ = input_variables
    if not messages or messages[0].role != "system":
        return False

    allowed_tool_names = [t.name for t in tools]
    summarized_intents = intent_plan or []
    capability_summary_injected = False
    intent_summary = (
        ", ".join(intent.user_visible_label for intent in summarized_intents[:4])
        or ", ".join(ordered_requested_families or [])
        or "direct_reply"
    )
    hint = "\n\n" + render_contract(
        "tool_runtime_summary",
        execution_path=execution_path or "fast",
        intent_summary=intent_summary,
        allowed_tools=", ".join(allowed_tool_names) or "none",
        prompt_budget=(
            execution_budget.max_prompt_tokens if execution_budget is not None else 0
        ),
        tool_round_budget=(
            execution_budget.max_tool_rounds if execution_budget is not None else 0
        ),
        elapsed_budget_ms=(
            execution_budget.max_elapsed_ms if execution_budget is not None else 0
        ),
    )
    hint += "\n\n" + render_contract("tool_usage_rules")
    continuation_hint = build_research_continuation_hint(
        continuation_context,
        render_contract=render_contract,
    )
    if continuation_hint:
        hint += continuation_hint
    if not skip_capability_summary:
        runtime_capability_hint = build_runtime_capability_hint(
            runtime_capability_summary=runtime_capability_summary,
            include_knowledge_base_hint=include_knowledge_base_hint,
            include_page_context_hint=include_page_context_hint,
            include_memory_hint=include_memory_hint,
            render_contract=render_contract,
        )
        if runtime_capability_hint:
            hint += runtime_capability_hint
            capability_summary_injected = True

    signature = hashlib.sha1(
        json.dumps(
            {
                "tools": allowed_tool_names,
                "intent_summary": intent_summary,
                "execution_path": execution_path or "fast",
                "budget": (
                    execution_budget.snapshot() if execution_budget is not None else None
                ),
                "runtime_capability_summary": dict(runtime_capability_summary or {}),
                "skip_capability_summary": bool(skip_capability_summary),
                "include_knowledge_base_hint": bool(include_knowledge_base_hint),
                "include_page_context_hint": bool(include_page_context_hint),
                "include_memory_hint": bool(include_memory_hint),
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    metadata = dict(messages[0].metadata or {})
    if metadata.get("runtime_summary_signature") == signature:
        return capability_summary_injected
    metadata["runtime_summary_signature"] = signature
    messages[0] = ChatMessage(
        role="system",
        content=messages[0].content + hint,
        metadata=metadata,
    )
    return capability_summary_injected


def build_page_operations_hint(
    *,
    input_variables: dict[str, Any] | None,
    tools: list[ToolDefinition] | None = None,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    """Build PAGE OPERATIONS hint from page context and available ui tools."""
    if not input_variables:
        return ""
    from app.ai.tools.semantic_defaults import (
        UI_DANGEROUS_PAGE_TOOL_NAMES,
        UI_READONLY_PAGE_TOOL_NAMES,
        UI_SAFE_WRITE_PAGE_TOOL_NAMES,
        page_context_available_ui_tools,
        page_context_payload,
    )

    page_ctx = page_context_payload(input_variables)
    if not isinstance(page_ctx, dict):
        return ""

    page_key = (page_ctx.get("page_key") or "").strip()
    if not page_key:
        return ""

    tool_names = [t.name for t in (tools or [])]
    available_ui_tools = page_context_available_ui_tools(
        page_ctx,
        available_tool_names=set(tool_names),
    )
    if not available_ui_tools:
        return ""

    readonly_tools = [
        name for name in available_ui_tools if name in UI_READONLY_PAGE_TOOL_NAMES
    ]
    action_tools = [
        name
        for name in available_ui_tools
        if name in {"ui_click", "ui_open_surface", "ui_list_interactables"}
    ]
    form_tools = [
        name
        for name in available_ui_tools
        if name in {"ui_get_form_state", "ui_set_field", "ui_fill_form"}
    ]
    submit_tools = [
        name for name in available_ui_tools if name in UI_DANGEROUS_PAGE_TOOL_NAMES
    ]
    safe_write_tools = [
        name
        for name in available_ui_tools
        if name in UI_SAFE_WRITE_PAGE_TOOL_NAMES and name not in action_tools
    ]

    return "\n\n" + render_contract(
        "page_operations_dedicated",
        page_key=page_key,
        readonly_tools=", ".join(readonly_tools),
        action_tools=", ".join(action_tools),
        safe_write_tools=", ".join(safe_write_tools),
        form_tools=", ".join(form_tools),
        submit_tools=", ".join(submit_tools),
    )


def deserialize_intent_plan(raw_intent_plan: Any) -> list[IntentPlan]:
    if not isinstance(raw_intent_plan, list):
        return []
    intent_plan: list[IntentPlan] = []
    for raw_intent in raw_intent_plan:
        if isinstance(raw_intent, IntentPlan):
            intent_plan.append(raw_intent)
            continue
        if not isinstance(raw_intent, dict):
            continue
        try:
            intent_plan.append(IntentPlan(**raw_intent))
        except TypeError:
            continue
    return intent_plan


def intent_plan_gating_flags(intent_plan: list[IntentPlan]) -> dict[str, bool]:
    flags = ContextPipelineOrchestrator.compute_intent_flags(intent_plan)
    return {
        "all_shortcircuit": bool(flags.all_shortcircuit),
        "has_page_intent": bool(flags.has_page_intent),
        "has_knowledge_intent": bool(flags.has_knowledge_intent),
        "has_memory_intent": bool(flags.has_memory_intent),
    }


def should_skip_capability_summary(
    *,
    diagnostics: dict[str, Any],
    intent_flags: dict[str, bool],
    force_capability_summary: bool,
) -> bool:
    return bool(diagnostics.get("dynamic_capability_awareness_enabled")) or (
        bool(intent_flags.get("all_shortcircuit")) and not force_capability_summary
    )


def resolve_capability_injection_decision(
    *,
    diagnostics: dict[str, Any],
    intent_flags: dict[str, bool],
    context_sources: list[Any] | None,
    capability_summary_injected: bool,
) -> dict[str, Any]:
    decision = dict(diagnostics.get("capability_injection_decision") or {})
    decision.setdefault("all_shortcircuit", bool(intent_flags.get("all_shortcircuit")))
    decision.setdefault("skills_injected", False)
    decision.setdefault("kb_injected", False)
    decision.setdefault("memory_injected", False)
    decision.setdefault("page_injected", False)
    decision.setdefault(
        "bypass_reason",
        "all_shortcircuit" if bool(intent_flags.get("all_shortcircuit")) else None,
    )

    active_context_source_kinds = {
        str(source.kind or "").strip()
        for source in (context_sources or [])
        if bool(getattr(source, "active", True))
    }
    decision["skills_injected"] = bool(
        capability_summary_injected and "skill" in active_context_source_kinds
    )
    decision["kb_injected"] = bool(
        decision["kb_injected"]
        or (
            capability_summary_injected
            and "knowledge_base" in active_context_source_kinds
            and bool(intent_flags.get("has_knowledge_intent"))
        )
    )
    decision["memory_injected"] = bool(
        decision["memory_injected"]
        or (
            capability_summary_injected
            and (
                "session_memory" in active_context_source_kinds
                or "long_term_memory" in active_context_source_kinds
            )
            and bool(intent_flags.get("has_memory_intent"))
        )
    )
    decision["page_injected"] = bool(
        decision["page_injected"]
        or (
            capability_summary_injected
            and "page_context" in active_context_source_kinds
            and bool(intent_flags.get("has_page_intent"))
        )
    )
    return decision


def is_capability_reporting_query(user_text: str | None) -> bool:
    normalized = " ".join(str(user_text or "").strip().lower().split())
    if not normalized:
        return False
    return any(term in normalized for term in _CAPABILITY_REPORTING_QUERY_TERMS)


def intent_completion_signals(
    family: str,
    *,
    allowed_tool_names: list[str],
    preferred_tool_names: list[str],
) -> list[str]:
    if family == "web_research":
        if "fetch_url" in allowed_tool_names:
            return ["fetch_url"]
        if "web_search" in allowed_tool_names:
            return ["web_search"]
    return list(allowed_tool_names or preferred_tool_names)


def build_web_research_hint(
    tools: list[ToolDefinition],
    *,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    tool_names = {t.name for t in tools}
    has_search = "web_search" in tool_names
    has_fetch = "fetch_url" in tool_names
    if not (has_search or has_fetch):
        return ""

    workflow = []
    if has_search:
        workflow.append("1) use web_search to find candidate sources")
    if has_fetch:
        next_step = "2" if has_search else "1"
        workflow.append(
            f"{next_step}) use fetch_url to read the most relevant page content"
        )

    compare_step = "3" if has_search and has_fetch else "2"
    workflow.append(
        f"{compare_step}) prefer official or primary sources, and compare more than one source when the user asks for current, recent, or high-stakes information"
    )

    return "\n\n" + render_contract(
        "web_research",
        workflow="; ".join(workflow),
    )


def build_weather_tools_hint(
    tools: list[ToolDefinition],
    *,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    tool_names = {t.name for t in tools}
    has_current = "get_current_weather" in tool_names
    has_forecast = "get_weather_forecast" in tool_names
    if not (has_current or has_forecast):
        return ""

    workflow: list[str] = []
    if has_current:
        workflow.append("use get_current_weather for current conditions")
    if has_forecast:
        workflow.append(
            "use get_weather_forecast for tomorrow, future days, or 7-day forecasts"
        )

    return "\n\n" + render_contract(
        "weather_tools",
        workflow="; ".join(workflow),
    )


def build_time_tools_hint(
    tools: list[ToolDefinition],
    *,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    tool_names = {t.name for t in tools}
    if "get_current_time" not in tool_names:
        return ""
    return "\n\n" + render_contract("time_tools")


def build_capability_reporting_hint(
    *,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    tool_names = [t.name for t in tools]
    ui_tools: list[str] = []
    if input_variables:
        from app.ai.tools.semantic_defaults import (
            page_context_available_ui_tools,
            page_context_payload,
        )

        page_ctx = page_context_payload(input_variables)
        if isinstance(page_ctx, dict):
            ui_tools = page_context_available_ui_tools(
                page_ctx,
                available_tool_names=set(tool_names),
            )

    tool_line = ", ".join(tool_names) if tool_names else "none"
    ui_tool_line = ", ".join(ui_tools) if ui_tools else "none"
    return "\n\n" + render_contract(
        "capability_reporting",
        tool_line=tool_line,
        ui_tool_line=ui_tool_line,
    )


def build_runtime_capability_hint(
    *,
    runtime_capability_summary: dict[str, Any] | None,
    include_knowledge_base_hint: bool = True,
    include_page_context_hint: bool = True,
    include_memory_hint: bool = True,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    summary = (
        dict(runtime_capability_summary)
        if isinstance(runtime_capability_summary, dict)
        else {}
    )
    normalized_skill_names: list[str] = []
    for name in summary.get("selected_skill_names") or []:
        text = str(name or "").strip()
        if text and text not in normalized_skill_names:
            normalized_skill_names.append(text)

    context_line = str(summary.get("context_line") or "").strip()
    if not normalized_skill_names and not context_line:
        return ""
    return "\n\n" + render_contract(
        "turn_capabilities",
        selected_skill_names=", ".join(normalized_skill_names),
        context_line=context_line,
        knowledge_base_hint=(
            include_knowledge_base_hint
            and bool(summary.get("knowledge_base_hint", False))
        ),
        page_context_hint=(
            include_page_context_hint and bool(summary.get("page_context_hint", False))
        ),
        memory_hint=(include_memory_hint and bool(summary.get("memory_hint", False))),
    )


def build_ordered_capability_hint(
    *,
    ordered_requested_families: list[str] | None,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
    allowed_tool_names_for_family: Callable[
        [str, list[ToolDefinition], dict[str, Any] | None],
        list[str],
    ],
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    ordered: list[str] = []
    for family in ordered_requested_families or []:
        normalized = str(family or "").strip()
        if not normalized or normalized == "none" or normalized in ordered:
            continue
        ordered.append(normalized)

    if len(ordered) <= 1:
        return ""

    label_map = {
        "page_ops": "page operations",
        "weather": "weather tools",
        "time_ops": "time tools",
        "web_research": "web research tools",
    }
    sequence_lines: list[str] = []
    for idx, family in enumerate(ordered, start=1):
        label = label_map.get(family, family.replace("_", " "))
        family_tools = allowed_tool_names_for_family(family, tools, input_variables)
        shown_tools = ", ".join(family_tools[:4]) if family_tools else "none"
        suffix = "..." if len(family_tools) > 4 else ""
        sequence_lines.append(f"{idx}. {label} (tools: {shown_tools}{suffix})")

    return "\n\n" + render_contract(
        "ordered_capability_intent",
        sequence_lines="\n".join(sequence_lines),
    )


def build_ordered_capability_hint_default(
    *,
    ordered_requested_families: list[str] | None,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
) -> str:
    from .tool_policy_helpers import (
        allowed_tool_names_for_family as _allowed_tool_names_for_family_impl,
    )

    return build_ordered_capability_hint(
        ordered_requested_families=ordered_requested_families,
        tools=tools,
        input_variables=input_variables,
        allowed_tool_names_for_family=_allowed_tool_names_for_family_impl,
    )


def build_research_continuation_hint(
    continuation: ResearchContinuationContext | None,
    *,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    if not continuation or not continuation.active:
        return ""
    if continuation.family != "web_research":
        return ""

    target = continuation.research_target_text
    intro = (
        "This turn continues the previous external web research task."
        if continuation.origin == "continuation"
        else "This turn is an external web research task."
    )
    instruction_lines = (
        "\n".join(f"- {text}" for text in continuation.research_instruction_texts)
        if continuation.research_instruction_texts
        else "- (no recent research instructions captured)"
    )
    extra_guidance = (
        "Search-result tool messages in the conversation history are candidate URL lists. "
        "If fetched detail pages is 0 and fetch_url is available, pick candidate URLs from those lists and fetch them before analysis.\n"
        if continuation.fetched_url_count == 0
        else ""
    )
    return "\n\n" + render_contract(
        "research_state",
        intro=intro,
        target=target or "(same target as previous turn)",
        instruction_lines=instruction_lines,
        recent_queries=(
            ", ".join(continuation.recent_web_queries)
            if continuation.recent_web_queries
            else "(none)"
        ),
        search_query_count=continuation.search_query_count,
        fetched_url_count=continuation.fetched_url_count,
        extra_guidance=extra_guidance.strip(),
    )
