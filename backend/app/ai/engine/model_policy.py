"""Model request policy helpers shared by sync and stream execution."""

from __future__ import annotations

from typing import Any

from app.ai.adapters.openai_compatible.capabilities import OpenAIProtocolCapabilities
from app.ai.adapters.openai_compatible.support.model_request_runtime import (
    OpenAIAdapterModelRequestMixin,
)
from app.ai.adapters.openai_compatible.support.native_web_search_policy import (
    supports_native_web_search_model,
)

FAST_PATH_REASONING_EFFORT = "low"
_HOSTED_WEB_SEARCH_CONTEXT_SIZE = "medium"


def _runtime_context_supports_native_web_search(runtime_context: Any | None) -> bool:
    if runtime_context is None:
        return False

    provider = getattr(runtime_context, "provider", None)
    provider_type = str(getattr(provider, "type", "") or "").strip()
    if provider_type != "openai_compatible":
        return False

    provider_config = (
        dict(getattr(provider, "config", {}) or {})
        if isinstance(getattr(provider, "config", None), dict)
        else {}
    )
    web_search_config = provider_config.get("web_search")
    if (
        isinstance(web_search_config, dict)
        and web_search_config.get("enabled") is False
    ):
        return False

    capabilities = OpenAIProtocolCapabilities.from_provider_config(
        provider_config=provider_config,
        configured_wire_api=provider_config.get("wire_api"),
    )
    if not capabilities.supports_wire_api("responses"):
        return False

    ai_model = getattr(runtime_context, "ai_model", None)
    model_config = getattr(ai_model, "config", None)
    effective_model_request = (
        OpenAIAdapterModelRequestMixin.resolve_effective_model_request(
            model=str(getattr(runtime_context, "model_code", "") or ""),
            model_config=model_config if isinstance(model_config, dict) else None,
            wire_api="responses",
        )
    )
    return supports_native_web_search_model(
        str(effective_model_request.get("upstream_model") or "")
    )


def _policy_requests_native_web_search_first(
    *,
    tool_use_policy: Any | None,
    tools: list[Any] | None,
) -> bool:
    _ = tools
    if tool_use_policy is None:
        return False
    return str(
        getattr(tool_use_policy, "family", "") or ""
    ).strip() == "web_research" and str(
        getattr(tool_use_policy, "reason", "") or ""
    ).startswith("native_web_search_first:")


def build_model_request_overrides(
    *,
    execution_path: str | None,
    tools: list[Any] | None,
    tool_use_policy: Any | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """Apply lightweight model overrides for fast, text-only rounds."""

    if _policy_requests_native_web_search_first(
        tool_use_policy=tool_use_policy,
        tools=tools,
    ) and _runtime_context_supports_native_web_search(runtime_context):
        return {
            "_runtime_force_protocol_path": "responses",
            "_runtime_hosted_web_search_required": True,
            "_runtime_hosted_web_search_context_size": (
                _HOSTED_WEB_SEARCH_CONTEXT_SIZE
            ),
        }

    normalized_path = str(execution_path or "").strip().lower()
    if normalized_path != "fast":
        return {}
    if tools:
        return {}
    return {
        "_runtime_reasoning_effort_override": FAST_PATH_REASONING_EFFORT,
    }


__all__ = ["FAST_PATH_REASONING_EFFORT", "build_model_request_overrides"]
