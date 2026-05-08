"""Request payload builders for OpenAI-compatible adapters."""

from __future__ import annotations

from typing import Any, Protocol

from app.ai.types import ChatMessage
from app.schemas.ai.invalid_ai_runtime_input import (
    INVALID_AI_PROVIDER_CONFIG_KEYS,
    is_invalid_ai_runtime_reference,
    normalize_ai_runtime_token,
)


class RequestPayloadBuilderAdapterProtocol(Protocol):
    config: dict[str, Any]
    provider_config: dict[str, Any]

    def resolve_effective_model_request(
        self,
        *,
        model: str,
        model_config: Any = None,
        wire_api: str | None = None,
    ) -> dict[str, Any]: ...

    async def _convert_messages_to_responses_input(
        self,
        messages: list[ChatMessage],
        *,
        supports_vision: bool = True,
        supports_audio: bool = False,
        supports_video: bool = False,
    ) -> list[dict[str, Any]]: ...


_RESPONSES_RESPONSE_ID_METADATA_KEY = "responses_response_id"


def _combine_system_instructions(messages: list[ChatMessage]) -> str:
    parts: list[str] = []
    for msg in messages:
        if msg.role != "system":
            continue
        text = str(msg.content or "").strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _exclude_system_messages(messages: list[ChatMessage]) -> list[ChatMessage]:
    return [msg for msg in messages if msg.role != "system"]


def _resolve_responses_continuation_anchor(
    messages: list[ChatMessage],
) -> tuple[int, str] | None:
    for index in range(len(messages) - 1, -1, -1):
        msg = messages[index]
        if msg.role != "assistant" or not msg.tool_calls:
            continue
        metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
        response_id = str(
            metadata.get(_RESPONSES_RESPONSE_ID_METADATA_KEY) or ""
        ).strip()
        if response_id:
            if not _is_safe_responses_tool_followup(
                messages=messages,
                anchor_index=index,
            ):
                return None
            return index, response_id
        return None
    return None


def _is_safe_responses_tool_followup(
    *,
    messages: list[ChatMessage],
    anchor_index: int,
) -> bool:
    trailing_messages = messages[anchor_index + 1 :]
    if not trailing_messages:
        return False

    saw_tool_output = False
    for msg in trailing_messages:
        if msg.role != "tool":
            return False
        saw_tool_output = True

    return saw_tool_output


def _drop_runtime_private_kwargs(runtime_kwargs: dict[str, Any]) -> None:
    for key in tuple(runtime_kwargs):
        normalized = normalize_ai_runtime_token(key)
        if (
            str(key).startswith("_runtime_")
            or normalized in INVALID_AI_PROVIDER_CONFIG_KEYS
            or is_invalid_ai_runtime_reference(key)
        ):
            runtime_kwargs.pop(key, None)


def _function_tools_only(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        tool
        for tool in tools
        if isinstance(tool, dict) and str(tool.get("type") or "").strip() == "function"
    ]


def build_chat_completions_request(
    *,
    adapter: RequestPayloadBuilderAdapterProtocol,
    openai_messages: list[dict[str, Any]],
    model: str,
    temperature: float,
    max_tokens: int | None,
    top_p: float,
    tools: list[dict] | None,
    tool_choice: str | None,
    stream: bool,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    runtime_kwargs = dict(kwargs)
    effective_request = runtime_kwargs.pop("_effective_model_request", None)
    model_config = runtime_kwargs.pop("model_config", None)
    runtime_kwargs.pop("_runtime_force_protocol_path", None)
    if effective_request is None:
        effective_request = adapter.resolve_effective_model_request(
            model=model,
            model_config=(
                model_config
                if model_config is not None
                else adapter.config.get("model_config")
            ),
            wire_api="chat_completions",
        )

    request_params: dict[str, Any] = {
        "model": effective_request["upstream_model"],
        "messages": openai_messages,
        "temperature": temperature,
        "top_p": top_p,
    }
    if max_tokens is not None:
        request_params["max_tokens"] = max_tokens
    if stream:
        request_params["stream"] = True
    filtered_tools = _function_tools_only(tools or [])
    if filtered_tools:
        request_params["tools"] = filtered_tools
        request_params["tool_choice"] = tool_choice or "auto"
    if runtime_kwargs.get("reasoning_effort") is None and "reasoning_effort" in (
        effective_request.get("effective_params", {})
    ):
        request_params["reasoning_effort"] = effective_request["effective_params"][
            "reasoning_effort"
        ]
    _drop_runtime_private_kwargs(runtime_kwargs)
    request_params.update(runtime_kwargs)
    return request_params


def supports_responses_reasoning_summary(
    *,
    model: str,
    reasoning_summary_model_prefixes: tuple[str, ...],
) -> bool:
    normalized = str(model or "").strip().lower()
    return any(
        normalized.startswith(prefix) for prefix in reasoning_summary_model_prefixes
    )


def build_responses_reasoning_config(
    *,
    model: str,
    explicit_reasoning: Any = None,
    reasoning_summary_model_prefixes: tuple[str, ...],
) -> Any:
    supports_summary = supports_responses_reasoning_summary(
        model=model,
        reasoning_summary_model_prefixes=reasoning_summary_model_prefixes,
    )

    if isinstance(explicit_reasoning, dict):
        if explicit_reasoning.get("summary") is not None:
            return explicit_reasoning
        if not supports_summary:
            return explicit_reasoning
        return {
            **explicit_reasoning,
            "summary": "auto",
        }

    if explicit_reasoning is not None:
        return explicit_reasoning
    if not supports_summary:
        return None
    return {"summary": "auto"}


def convert_tools_for_responses(tools: list[dict]) -> list[dict]:
    converted: list[dict] = []

    for tool in tools:
        if not isinstance(tool, dict):
            continue
        if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
            function = tool["function"]
            func_name = function.get("name", "")
            converted.append(
                {
                    "type": "function",
                    "name": func_name,
                    "description": function.get("description"),
                    "parameters": function.get("parameters"),
                }
            )
            continue
    return converted


async def build_responses_request(
    *,
    adapter: RequestPayloadBuilderAdapterProtocol,
    messages: list[ChatMessage],
    model: str,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    top_p: float = 1.0,
    tools: list[dict] | None = None,
    tool_choice: str | None = None,
    stream: bool = False,
    kwargs: dict[str, Any],
    reasoning_summary_model_prefixes: tuple[str, ...],
) -> dict[str, Any]:
    runtime_kwargs = dict(kwargs)
    supports_vision = runtime_kwargs.pop("supports_vision", True)
    supports_audio = runtime_kwargs.pop("supports_audio", False)
    supports_video = runtime_kwargs.pop("supports_video", False)
    explicit_reasoning = runtime_kwargs.pop("reasoning", None)
    effective_request = runtime_kwargs.pop("_effective_model_request", None)
    model_config = runtime_kwargs.pop("model_config", None)
    runtime_kwargs.pop("_runtime_force_protocol_path", None)
    runtime_kwargs.pop("previous_response_id", None)
    if effective_request is None:
        effective_request = adapter.resolve_effective_model_request(
            model=model,
            model_config=(
                model_config
                if model_config is not None
                else adapter.config.get("model_config")
            ),
            wire_api="responses",
        )

    if explicit_reasoning is None and "reasoning" in (
        effective_request.get("effective_params", {})
    ):
        explicit_reasoning = effective_request["effective_params"]["reasoning"]

    continuation_anchor = _resolve_responses_continuation_anchor(messages)
    continuation_input_messages = messages
    request_params: dict[str, Any] = {
        "model": effective_request["upstream_model"],
        "temperature": temperature,
        "top_p": top_p,
    }
    instructions = _combine_system_instructions(messages)
    if instructions:
        request_params["instructions"] = instructions
    if continuation_anchor is not None and not stream:
        anchor_index, response_id = continuation_anchor
        continuation_input_messages = _exclude_system_messages(
            messages[anchor_index + 1 :]
        )
        request_params["previous_response_id"] = response_id
    else:
        continuation_input_messages = _exclude_system_messages(messages)

    request_params["input"] = await adapter._convert_messages_to_responses_input(
        continuation_input_messages,
        supports_vision=supports_vision,
        supports_audio=supports_audio,
        supports_video=supports_video,
    )
    if max_tokens is not None:
        request_params["max_output_tokens"] = max_tokens
    if stream:
        request_params["stream"] = True
    converted_tools = convert_tools_for_responses(tools) if tools else []
    if converted_tools:
        request_params["tools"] = converted_tools
        if tool_choice:
            request_params["tool_choice"] = tool_choice

    reasoning = build_responses_reasoning_config(
        model=model,
        explicit_reasoning=explicit_reasoning,
        reasoning_summary_model_prefixes=reasoning_summary_model_prefixes,
    )
    if reasoning is not None:
        request_params["reasoning"] = reasoning

    _drop_runtime_private_kwargs(runtime_kwargs)
    request_params.update(runtime_kwargs)
    return request_params


__all__ = [
    "RequestPayloadBuilderAdapterProtocol",
    "build_chat_completions_request",
    "build_responses_reasoning_config",
    "build_responses_request",
    "convert_tools_for_responses",
    "supports_responses_reasoning_summary",
]
