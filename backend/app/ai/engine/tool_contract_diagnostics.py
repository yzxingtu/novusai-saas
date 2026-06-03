"""Tool contract diagnostics helpers."""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage, ChatResponse
from app.core.logging import LogManager

from .base_helpers import truncate_preview as _truncate_preview_impl
from .tool_contract_evidence import collect_tool_family_evidence
from .types import ToolUsePolicy

logger = LogManager.get_logger("ai.engine")


def _extract_last_user_text(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if str(getattr(message, "role", "") or "") != "user":
            continue
        text = str(getattr(message, "content", "") or "").strip()
        if text:
            return text
    return ""


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
    continuation: Any | None = None,
    truncate_preview,
) -> None:
    if not tools:
        return

    response_text = (
        (response.message.content or "").strip() if response is not None else ""
    )
    current_user_text = _extract_last_user_text(messages)
    trace_id = ""
    try:
        from app.middleware.trace import trace_id_var

        trace_id = trace_id_var.get() or ""
    except Exception:
        trace_id = ""

    family_evidence = collect_tool_family_evidence(messages)
    status = {
        "retrying": "policy_retry_started",
        "succeeded": "policy_retry_succeeded",
        "failed": "policy_retry_failed",
        "logged": "policy_logged_only",
        "no_retry": "policy_loaded_but_no_retry",
    }.get(retry_result, retry_result or "policy_unknown")
    logger.warning(
        "Tool contract breach: status={} type={} retry_result={} agent_id={} conversation_id={} trace_id={} family={} tool_choice={} allowed_tool_names={} current_user_text={} response_preview={} family_evidence={}",
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
        family_evidence,
    )


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
    continuation: Any | None = None,
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
