"""Helpers for resolving LLM call context outside the base engine facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.tools.types import ToolDefinition, to_openai_tools
from app.ai.types import ChatMessage, ChatResponse
from app.models.ai.agent import Agent

from .types import ToolUsePolicy


@dataclass(frozen=True)
class LLMCallContext:
    provider_code: str
    model_code: str
    routed_model_id: int | None
    route_reason: str | None
    supports_vision: bool
    supports_audio: bool
    supports_video: bool


@dataclass(frozen=True)
class PreparedLLMCall:
    effective_policy: ToolUsePolicy
    llm_call_context: LLMCallContext
    openai_tools: list[dict[str, Any]] | None
    gateway_kwargs: dict[str, Any]


def build_effective_tool_policy(
    *,
    tools: list[ToolDefinition] | None,
    tool_use_policy: ToolUsePolicy | None,
) -> ToolUsePolicy:
    if tool_use_policy is not None:
        return tool_use_policy
    return ToolUsePolicy(
        family="none",
        mode="auto" if tools else "none",
        allowed_tool_names=[tool.name for tool in (tools or [])],
        retry_on_contract_breach=False,
        reason="implicit_auto",
    )


async def resolve_llm_call_context(
    *,
    db: Any,
    agent: Agent,
    route_result: Any | None,
) -> LLMCallContext:
    if route_result is not None and getattr(route_result, "is_overridden", False):
        provider_code = route_result.provider_code or ""
        model_code = route_result.model_code or ""
        routed_model_id = int(getattr(route_result, "model_id", 0) or 0) or None
        route_reason = route_result.reason or None
        model_id = int(getattr(route_result, "model_id", 0) or 0)
        route_model_obj = None
        if model_id:
            from app.repositories.ai.model_repository import AIModelRepository

            model_repo = AIModelRepository(db)
            route_model_obj = await model_repo.get_active_with_provider(model_id)
        if route_model_obj is not None:
            return LLMCallContext(
                provider_code=provider_code,
                model_code=model_code,
                routed_model_id=routed_model_id,
                route_reason=route_reason,
                supports_vision=bool(route_model_obj.supports_vision),
                supports_audio=bool(
                    getattr(route_model_obj, "supports_audio", False)
                ),
                supports_video=bool(
                    getattr(route_model_obj, "supports_video", False)
                ),
            )

        reason_str = route_result.reason or ""
        return LLMCallContext(
            provider_code=provider_code,
            model_code=model_code,
            routed_model_id=routed_model_id,
            route_reason=route_reason,
            supports_vision="vision" in reason_str,
            supports_audio="audio" in reason_str,
            supports_video="video" in reason_str,
        )

    model_obj = agent.model
    return LLMCallContext(
        provider_code=model_obj.provider.code if model_obj and model_obj.provider else "",
        model_code=model_obj.code if model_obj else "",
        routed_model_id=None,
        route_reason=None,
        supports_vision=bool(model_obj.supports_vision) if model_obj else False,
        supports_audio=bool(getattr(model_obj, "supports_audio", False))
        if model_obj
        else False,
        supports_video=bool(getattr(model_obj, "supports_video", False))
        if model_obj
        else False,
    )


def prune_messages_for_model_capabilities(
    messages: list[ChatMessage],
    *,
    supports_vision: bool,
    supports_audio: bool,
    supports_video: bool,
) -> None:
    for msg in messages:
        if not msg.attachments:
            continue
        kept = [
            attachment
            for attachment in msg.attachments
            if not (
                (attachment.get("type") == "image" and not supports_vision)
                or (attachment.get("type") == "audio" and not supports_audio)
                or (attachment.get("type") == "video" and not supports_video)
            )
        ]
        msg.attachments = kept if kept else None


async def prepare_llm_gateway_call(
    *,
    db: Any,
    agent: Agent,
    messages: list[ChatMessage],
    tools: list[ToolDefinition] | None,
    all_tool_names: list[str] | None,
    tool_use_policy: ToolUsePolicy | None,
    breach_retry_result: str | None,
    tenant_id: int | None,
    user_id: int | None,
    conversation_id: int | None,
    billing_context: dict[str, Any] | None,
    route_result: Any | None,
    log_user_type: str | None,
) -> PreparedLLMCall:
    openai_tools = to_openai_tools(tools) if tools else None
    effective_policy = build_effective_tool_policy(
        tools=tools,
        tool_use_policy=tool_use_policy,
    )
    llm_call_context = await resolve_llm_call_context(
        db=db,
        agent=agent,
        route_result=route_result,
    )
    prune_messages_for_model_capabilities(
        messages,
        supports_vision=llm_call_context.supports_vision,
        supports_audio=llm_call_context.supports_audio,
        supports_video=llm_call_context.supports_video,
    )
    gateway_kwargs = {
        "provider_code": llm_call_context.provider_code,
        "messages": messages,
        "model": llm_call_context.model_code,
        "temperature": agent.temperature,
        "max_tokens": agent.max_tokens,
        "top_p": agent.top_p or 1.0,
        "tools": openai_tools,
        "tool_choice": (
            effective_policy.mode
            if openai_tools and effective_policy.mode in {"auto", "required"}
            else None
        ),
        "all_tool_names": all_tool_names or [tool.name for tool in (tools or [])],
        "tool_use_policy_family": effective_policy.family,
        "tool_use_policy_mode": effective_policy.mode,
        "allowed_tool_names": effective_policy.allowed_tool_names,
        "breach_retry_result": breach_retry_result,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "user_type": log_user_type,
        "agent_id": getattr(agent, "id", None),
        "conversation_id": conversation_id,
        "billing_context": billing_context,
        "routed_model_id": llm_call_context.routed_model_id,
        "route_reason": llm_call_context.route_reason,
        "supports_vision": llm_call_context.supports_vision,
        "supports_audio": llm_call_context.supports_audio,
        "supports_video": llm_call_context.supports_video,
    }
    return PreparedLLMCall(
        effective_policy=effective_policy,
        llm_call_context=llm_call_context,
        openai_tools=openai_tools,
        gateway_kwargs=gateway_kwargs,
    )


def apply_llm_response_metadata(
    response: ChatResponse,
    *,
    llm_call_context: LLMCallContext,
) -> ChatResponse:
    metadata = dict(getattr(response, "metadata", {}) or {})
    if llm_call_context.routed_model_id is not None:
        metadata["routed_model_id"] = llm_call_context.routed_model_id
    if llm_call_context.route_reason:
        metadata["route_reason"] = llm_call_context.route_reason
    response.metadata = metadata
    return response


__all__ = [
    "LLMCallContext",
    "PreparedLLMCall",
    "apply_llm_response_metadata",
    "build_effective_tool_policy",
    "prepare_llm_gateway_call",
    "prune_messages_for_model_capabilities",
    "resolve_llm_call_context",
]
