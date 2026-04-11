"""Build runtime-v2 conversation entrypoint plans without embedding execution."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.ai.adapters import AdapterRegistry
from app.ai.runtime import ConversationQueryEngine
from app.ai.tools.types import ToolDefinition, to_openai_tools
from app.ai.types import ChatMessage, messages_to_dicts
from app.core.runtime_identity import get_runtime_identity_tag

from .conversation_helpers import (
    serialize_context_sources as _serialize_context_sources,
)
from .conversation_runtime_accounting import (
    ConversationRuntimeAccounting,
    ConversationRuntimeAuditContext,
    ConversationRuntimeRequestContext,
)
from .conversation_runtime_preflight import ConversationRuntimeContext
from .model_policy import build_model_request_overrides
from .types import ToolUsePolicy


@dataclass(frozen=True)
class ConversationRuntimeEntrypointPlan:
    runtime_context: ConversationRuntimeContext
    query_engine: ConversationQueryEngine
    accounting: ConversationRuntimeAccounting
    request_context: ConversationRuntimeRequestContext
    audit_context: ConversationRuntimeAuditContext
    request_log_data: dict[str, Any]
    runtime_context_sources: list[dict[str, Any]]
    selected_tool_names: list[str]
    resolved_all_tool_names: list[str]
    openai_tools: list[dict[str, Any]] | None
    effective_policy: ToolUsePolicy
    effective_tool_choice: str | None
    request_extra_kwargs: dict[str, Any]


def _build_request_context(
    *,
    messages: list[ChatMessage],
    agent: Any,
    openai_tools: list[dict[str, Any]] | None,
    effective_tool_choice: str | None,
    selected_tool_names: list[str],
    resolved_all_tool_names: list[str],
    effective_policy: ToolUsePolicy,
    breach_retry_result: str | None,
    request_log_data: dict[str, Any],
) -> ConversationRuntimeRequestContext:
    return ConversationRuntimeRequestContext(
        messages=messages,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        top_p=agent.top_p or 1.0,
        openai_tools=openai_tools,
        effective_tool_choice=effective_tool_choice,
        selected_tool_names=selected_tool_names,
        all_tool_names=resolved_all_tool_names,
        tool_use_policy=effective_policy,
        breach_retry_result=breach_retry_result,
        request_log_data=request_log_data,
    )


def _build_audit_context(
    *,
    tenant_id: int | None,
    user_id: int | None,
    log_user_type: str | None,
    agent: Any,
    conversation_id: int | None,
    billing_context: dict[str, Any] | None,
    runtime_context_sources: list[dict[str, Any]],
) -> ConversationRuntimeAuditContext:
    return ConversationRuntimeAuditContext(
        tenant_id=tenant_id,
        user_id=user_id,
        log_user_type=log_user_type,
        agent_id=getattr(agent, "id", None),
        conversation_id=conversation_id,
        billing_context=billing_context,
        context_sources=runtime_context_sources,
    )


def _resolve_effective_policy(
    *,
    tools: list[ToolDefinition] | None,
    tool_use_policy: ToolUsePolicy | None,
    implicit_auto_default: bool,
) -> ToolUsePolicy:
    if tool_use_policy is not None:
        return tool_use_policy
    if implicit_auto_default:
        return ToolUsePolicy(
            family="none",
            mode="auto" if tools else "none",
            allowed_tool_names=[tool.name for tool in (tools or [])],
            retry_on_contract_breach=False,
            reason="implicit_auto",
        )
    return ToolUsePolicy()


async def _prepare_runtime_context(
    *,
    runtime_context: ConversationRuntimeContext | None,
    runtime_preparer: Callable[..., Awaitable[ConversationRuntimeContext]] | None,
    engine: Any,
    agent: Any,
    messages: list[ChatMessage],
    tenant_id: int | None,
    route_result: Any | None,
    skip_metering_preflight: bool,
) -> ConversationRuntimeContext:
    if runtime_context is not None:
        return runtime_context
    if runtime_preparer is None:
        raise ValueError("runtime_preparer is required when runtime_context is absent")
    return await runtime_preparer(
        engine,
        agent=agent,
        messages=messages,
        tenant_id=tenant_id,
        route_result=route_result,
        skip_metering_preflight=skip_metering_preflight,
    )


def _build_query_engine(
    *,
    runtime_context: ConversationRuntimeContext,
    db: Any,
    tenant_id: int | None,
    adapter_registry: Any,
    query_engine_cls: Any,
    effective_tool_choice: str | None,
) -> ConversationQueryEngine:
    provider = runtime_context.provider
    api_key = runtime_context.api_key
    ai_model = runtime_context.ai_model
    adapter = adapter_registry.create_adapter(
        provider_type=provider.type,
        api_key=api_key.decrypt_key(),
        base_url=provider.base_url,
        provider_config=provider.config,
        internal_db=db,
        internal_tenant_id=tenant_id,
        model_config=getattr(ai_model, "config", None),
    )
    return query_engine_cls(
        adapter=adapter,
        strict_contract=(effective_tool_choice == "required"),
    )


def _build_stream_request_log_data(
    *,
    messages: list[ChatMessage],
    agent: Any,
    openai_tools: list[dict[str, Any]] | None,
    effective_tool_choice: str | None,
    selected_tool_names: list[str],
    resolved_all_tool_names: list[str],
    effective_policy: ToolUsePolicy,
    breach_retry_result: str | None,
) -> dict[str, Any]:
    request_log_data = {
        "_stream": True,
        "messages": messages_to_dicts(messages),
        "temperature": agent.temperature,
        "max_tokens": agent.max_tokens,
        "top_p": agent.top_p or 1.0,
        "tools": openai_tools,
        "tool_choice": effective_tool_choice,
        "selected_tool_names": selected_tool_names,
        "all_tool_names": resolved_all_tool_names,
        "tool_use_policy": {
            "family": effective_policy.family,
            "mode": effective_policy.mode,
            "allowed_tool_names": effective_policy.allowed_tool_names,
        },
    }
    if breach_retry_result:
        request_log_data["breach_retry_result"] = breach_retry_result
    if effective_policy.reason.startswith(("capability_denial:", "required_retry:")):
        request_log_data["breach_retry_result"] = "contract_retry"
    return request_log_data


def _build_query_request_log_data(
    *,
    messages: list[ChatMessage],
    agent: Any,
    openai_tools: list[dict[str, Any]] | None,
    effective_tool_choice: str | None,
    selected_tool_names: list[str],
    resolved_all_tool_names: list[str],
    effective_policy: ToolUsePolicy,
    breach_retry_result: str | None,
    execution_path: str | None,
) -> dict[str, Any]:
    return {
        "_runtime_v2_non_stream": True,
        "messages": messages_to_dicts(messages),
        "temperature": agent.temperature,
        "max_tokens": agent.max_tokens,
        "top_p": agent.top_p or 1.0,
        "tools": openai_tools,
        "tool_choice": effective_tool_choice,
        "selected_tool_names": selected_tool_names,
        "all_tool_names": resolved_all_tool_names,
        "tool_use_policy": {
            "family": effective_policy.family,
            "mode": effective_policy.mode,
            "allowed_tool_names": effective_policy.allowed_tool_names,
        },
        "breach_retry_result": breach_retry_result,
        "execution_path": execution_path,
    }


def _warn_missing_stream_tool_policy(
    *,
    engine_logger: Any,
    openai_tools: list[dict[str, Any]] | None,
    effective_tool_choice: str | None,
    conversation_id: int | None,
    agent: Any,
) -> None:
    if (
        not openai_tools
        or effective_tool_choice
        or not any(
            isinstance(tool, dict)
            and (tool.get("function", {}) or {}).get("name")
            in {"web_search", "fetch_url"}
            for tool in openai_tools
        )
    ):
        return
    if engine_logger is None:
        return
    engine_logger.warning(
        "Tool policy not loaded: status=policy_not_loaded runtime={} conversation_id={} agent_id={} tool_names={}",
        get_runtime_identity_tag(),
        conversation_id,
        getattr(agent, "id", None),
        [
            (tool.get("function", {}) or {}).get("name")
            for tool in openai_tools
            if isinstance(tool, dict)
        ],
    )


async def build_runtime_query_entrypoint_plan(
    engine: Any,
    *,
    agent: Any,
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
    context_sources: list[Any] | None,
    execution_path: str | None,
    extra_kwargs: dict[str, Any] | None,
    runtime_preparer: Callable[..., Awaitable[ConversationRuntimeContext]],
    adapter_registry: Any = AdapterRegistry,
    query_engine_cls: Any = ConversationQueryEngine,
) -> ConversationRuntimeEntrypointPlan:
    runtime_context = await _prepare_runtime_context(
        runtime_context=None,
        runtime_preparer=runtime_preparer,
        engine=engine,
        agent=agent,
        messages=messages,
        tenant_id=tenant_id,
        route_result=route_result,
        skip_metering_preflight=True,
    )
    openai_tools = to_openai_tools(tools) if tools else None
    effective_policy = _resolve_effective_policy(
        tools=tools,
        tool_use_policy=tool_use_policy,
        implicit_auto_default=True,
    )
    effective_tool_choice = (
        effective_policy.mode
        if openai_tools and effective_policy.mode in {"auto", "required"}
        else None
    )
    selected_tool_names = [tool.name for tool in (tools or [])]
    resolved_all_tool_names = all_tool_names or list(selected_tool_names)
    request_log_data = _build_query_request_log_data(
        messages=messages,
        agent=agent,
        openai_tools=openai_tools,
        effective_tool_choice=effective_tool_choice,
        selected_tool_names=selected_tool_names,
        resolved_all_tool_names=resolved_all_tool_names,
        effective_policy=effective_policy,
        breach_retry_result=breach_retry_result,
        execution_path=execution_path,
    )
    runtime_context_sources = _serialize_context_sources(context_sources)
    query_engine = _build_query_engine(
        runtime_context=runtime_context,
        db=engine.db,
        tenant_id=tenant_id,
        adapter_registry=adapter_registry,
        query_engine_cls=query_engine_cls,
        effective_tool_choice=effective_tool_choice,
    )
    accounting = ConversationRuntimeAccounting(
        gateway=engine.gateway,
        db=engine.db,
    )
    request_context = _build_request_context(
        messages=messages,
        agent=agent,
        openai_tools=openai_tools,
        effective_tool_choice=effective_tool_choice,
        selected_tool_names=selected_tool_names,
        resolved_all_tool_names=resolved_all_tool_names,
        effective_policy=effective_policy,
        breach_retry_result=breach_retry_result,
        request_log_data=request_log_data,
    )
    audit_context = _build_audit_context(
        tenant_id=tenant_id,
        user_id=user_id,
        log_user_type=log_user_type,
        agent=agent,
        conversation_id=conversation_id,
        billing_context=billing_context,
        runtime_context_sources=runtime_context_sources,
    )
    return ConversationRuntimeEntrypointPlan(
        runtime_context=runtime_context,
        query_engine=query_engine,
        accounting=accounting,
        request_context=request_context,
        audit_context=audit_context,
        request_log_data=request_log_data,
        runtime_context_sources=runtime_context_sources,
        selected_tool_names=selected_tool_names,
        resolved_all_tool_names=resolved_all_tool_names,
        openai_tools=openai_tools,
        effective_policy=effective_policy,
        effective_tool_choice=effective_tool_choice,
        request_extra_kwargs=dict(extra_kwargs or {}),
    )


async def build_runtime_stream_entrypoint_plan(
    engine: Any,
    *,
    agent: Any,
    messages: list[ChatMessage],
    tenant_id: int | None = None,
    conversation_id: int | None = None,
    route_result: Any | None = None,
    tools: list[ToolDefinition] | None = None,
    execution_path: str | None = None,
    user_id: int | None = None,
    log_user_type: str | None = None,
    billing_context: dict[str, Any] | None = None,
    runtime_context: ConversationRuntimeContext | None = None,
    all_tool_names: list[str] | None = None,
    context_sources: list[Any] | None = None,
    tool_use_policy: ToolUsePolicy | None = None,
    breach_retry_result: str | None = None,
    runtime_preparer: Callable[..., Awaitable[ConversationRuntimeContext]] | None = None,
    adapter_registry: Any = AdapterRegistry,
    query_engine_cls: Any = ConversationQueryEngine,
    model_request_override_builder: Any = build_model_request_overrides,
    engine_logger: Any = None,
) -> ConversationRuntimeEntrypointPlan:
    runtime_context = await _prepare_runtime_context(
        runtime_context=runtime_context,
        runtime_preparer=runtime_preparer,
        engine=engine,
        agent=agent,
        messages=messages,
        tenant_id=tenant_id,
        route_result=route_result,
        skip_metering_preflight=False,
    )
    openai_tools = to_openai_tools(tools) if tools else None
    effective_policy = _resolve_effective_policy(
        tools=tools,
        tool_use_policy=tool_use_policy,
        implicit_auto_default=False,
    )
    effective_tool_choice = (
        effective_policy.mode
        if openai_tools and effective_policy.mode in {"auto", "required"}
        else None
    )
    selected_tool_names = [tool.name for tool in (tools or [])]
    resolved_all_tool_names = all_tool_names or list(selected_tool_names)
    request_log_data = _build_stream_request_log_data(
        messages=messages,
        agent=agent,
        openai_tools=openai_tools,
        effective_tool_choice=effective_tool_choice,
        selected_tool_names=selected_tool_names,
        resolved_all_tool_names=resolved_all_tool_names,
        effective_policy=effective_policy,
        breach_retry_result=breach_retry_result,
    )
    _warn_missing_stream_tool_policy(
        engine_logger=engine_logger,
        openai_tools=openai_tools,
        effective_tool_choice=effective_tool_choice,
        conversation_id=conversation_id,
        agent=agent,
    )
    runtime_context_sources = _serialize_context_sources(context_sources)
    query_engine = _build_query_engine(
        runtime_context=runtime_context,
        db=engine.db,
        tenant_id=tenant_id,
        adapter_registry=adapter_registry,
        query_engine_cls=query_engine_cls,
        effective_tool_choice=effective_tool_choice,
    )
    accounting = ConversationRuntimeAccounting(
        gateway=engine.gateway,
        db=engine.db,
    )
    request_context = _build_request_context(
        messages=messages,
        agent=agent,
        openai_tools=openai_tools,
        effective_tool_choice=effective_tool_choice,
        selected_tool_names=selected_tool_names,
        resolved_all_tool_names=resolved_all_tool_names,
        effective_policy=effective_policy,
        breach_retry_result=request_log_data.get("breach_retry_result"),
        request_log_data=request_log_data,
    )
    audit_context = _build_audit_context(
        tenant_id=tenant_id,
        user_id=user_id,
        log_user_type=log_user_type,
        agent=agent,
        conversation_id=conversation_id,
        billing_context=billing_context,
        runtime_context_sources=runtime_context_sources,
    )
    return ConversationRuntimeEntrypointPlan(
        runtime_context=runtime_context,
        query_engine=query_engine,
        accounting=accounting,
        request_context=request_context,
        audit_context=audit_context,
        request_log_data=request_log_data,
        runtime_context_sources=runtime_context_sources,
        selected_tool_names=selected_tool_names,
        resolved_all_tool_names=resolved_all_tool_names,
        openai_tools=openai_tools,
        effective_policy=effective_policy,
        effective_tool_choice=effective_tool_choice,
        request_extra_kwargs=dict(
            model_request_override_builder(
                execution_path=execution_path,
                tools=tools,
            )
        ),
    )


__all__ = [
    "ConversationRuntimeEntrypointPlan",
    "build_runtime_query_entrypoint_plan",
    "build_runtime_stream_entrypoint_plan",
]
