"""Tool contract diagnostics helpers."""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage, ChatResponse
from app.core.logging import LogManager

from .base_helpers import truncate_preview as _truncate_preview_impl
from .tool_contract_evidence import collect_tool_family_evidence
from .tool_policy_helpers import build_required_policy_for_family
from .turn_research_helpers import (
    collect_web_research_evidence,
    extract_last_user_text,
    is_title_only_fetch_response,
)
from .types import ResearchContinuationContext, ToolUsePolicy

logger = LogManager.get_logger("ai.engine")


def log_tool_contract_diagnostics(
    *,
    agent: Any,
    messages: list[ChatMessage],
    response: ChatResponse | None,
    tools: list[ToolDefinition],
    policy: ToolUsePolicy,
    conversation_id: int | None,
    breach_type: str,
    retry_result: str,
    continuation: ResearchContinuationContext | None = None,
    truncate_preview,
) -> None:
    if not tools:
        return

    response_text = (response.message.content or "").strip() if response is not None else ""
    current_user_text = extract_last_user_text(messages)
    target_text = (
        continuation.research_target_text
        if continuation and continuation.research_target_text
        else ""
    )
    trace_id = ""
    try:
        from app.middleware.trace import trace_id_var

        trace_id = trace_id_var.get() or ""
    except Exception:
        trace_id = ""

    family_evidence = collect_tool_family_evidence(messages)
    search_queries, fetched_urls = collect_web_research_evidence(messages)
    status = {
        "retrying": "policy_retry_started",
        "succeeded": "policy_retry_succeeded",
        "failed": "policy_retry_failed",
        "logged": "policy_logged_only",
        "no_retry": "policy_loaded_but_no_retry",
    }.get(retry_result, retry_result or "policy_unknown")
    logger.warning(
        "Tool contract breach: status={} type={} retry_result={} agent_id={} conversation_id={} trace_id={} family={} tool_choice={} allowed_tool_names={} current_user_text={} response_preview={} research_target={} family_evidence={} search_query_count={} fetched_url_count={}",
        status,
        breach_type,
        retry_result,
        getattr(agent, "id", None),
        conversation_id,
        trace_id,
        policy.family,
        policy.mode,
        policy.allowed_tool_names,
        truncate_preview(current_user_text),
        truncate_preview(response_text),
        truncate_preview(target_text),
        family_evidence,
        len(search_queries),
        len(fetched_urls),
    )


def log_web_research_contract_diagnostics(
    *,
    agent: Any,
    messages: list[ChatMessage],
    response: ChatResponse,
    tools: list[ToolDefinition],
    continuation: ResearchContinuationContext | None,
    conversation_id: int | None,
    truncate_preview,
) -> None:
    if not tools:
        return

    tool_names = [tool.name for tool in tools]
    if "web_search" not in tool_names:
        return

    response_text = (response.message.content or "").strip()
    search_queries, fetched_urls = collect_web_research_evidence(messages)
    search_count = len(search_queries)
    fetch_count = len(fetched_urls)

    def _emit(breach_type: str) -> None:
        log_tool_contract_diagnostics(
            agent=agent,
            messages=messages,
            response=response,
            tools=tools,
            policy=build_required_policy_for_family(
                "web_research",
                tools,
                None,
                reason=breach_type,
            ),
            conversation_id=conversation_id,
            breach_type=breach_type,
            retry_result="logged",
            continuation=continuation,
            truncate_preview=truncate_preview,
        )

    if not continuation or not continuation.active:
        return
    if response.tool_calls or not response_text:
        return

    if search_count == 0:
        _emit("web_research_capability_denial_or_no_tool_use")
        return

    if "fetch_url" in tool_names and search_count > 0 and fetch_count == 0:
        _emit("web_research_summary_without_fetch")
        return
    if is_title_only_fetch_response(
        messages=messages,
        response_text=response_text,
        user_text=extract_last_user_text(messages),
    ):
        _emit("web_research_title_only_after_fetch")


def log_tool_contract_diagnostics_default(
    *,
    agent: Any,
    messages: list[ChatMessage],
    response: ChatResponse | None,
    tools: list[ToolDefinition],
    policy: ToolUsePolicy,
    conversation_id: int | None,
    breach_type: str,
    retry_result: str,
    continuation: ResearchContinuationContext | None = None,
) -> None:
    log_tool_contract_diagnostics(
        agent=agent,
        messages=messages,
        response=response,
        tools=tools,
        policy=policy,
        conversation_id=conversation_id,
        breach_type=breach_type,
        retry_result=retry_result,
        continuation=continuation,
        truncate_preview=_truncate_preview_impl,
    )


def log_web_research_contract_diagnostics_default(
    *,
    agent: Any,
    messages: list[ChatMessage],
    response: ChatResponse,
    tools: list[ToolDefinition],
    continuation: ResearchContinuationContext | None,
    conversation_id: int | None,
) -> None:
    log_web_research_contract_diagnostics(
        agent=agent,
        messages=messages,
        response=response,
        tools=tools,
        continuation=continuation,
        conversation_id=conversation_id,
        truncate_preview=_truncate_preview_impl,
    )
