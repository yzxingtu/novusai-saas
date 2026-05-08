"""
Adapter support helpers for the AI gateway facade.
"""

from __future__ import annotations

from typing import Any

from app.ai.adapters.openai_adapter import OpenAIAdapter
from app.ai.adapters.openai_compatible.capabilities import OpenAIProtocolCapabilities
from app.models.ai import AIModel, AIProvider


def build_adapter_extra(
    *,
    db: Any,
    ai_model: AIModel | None,
    tenant_id: int | None,
) -> dict[str, object | None]:
    return {
        "internal_db": db,
        "internal_tenant_id": tenant_id,
        "model_config": getattr(ai_model, "config", None),
    }


def resolve_effective_model_request(
    *,
    provider: AIProvider,
    ai_model: AIModel | None,
    model_code: str,
    wire_api: str | None = None,
) -> dict[str, Any]:
    if provider.type == "openai_compatible":
        return OpenAIAdapter.resolve_effective_model_request(
            model=model_code,
            model_config=getattr(ai_model, "config", None),
            wire_api=wire_api,
        )
    return {
        "logical_model_code": model_code,
        "upstream_model": model_code,
        "reasoning_effort": None,
        "effective_params": {},
        "applied_overrides": [],
        "ignored_overrides": [],
        "ignore_reasons": {},
        "override_source": "model_code",
    }


def resolve_provider_primary_wire_api(provider: AIProvider) -> str:
    if provider.type != "openai_compatible":
        return "chat_completions"
    capabilities = OpenAIProtocolCapabilities.from_provider_config(
        provider_config=provider.config if isinstance(provider.config, dict) else {},
        configured_wire_api=None,
    )
    return capabilities.primary_wire_api


__all__ = [
    "build_adapter_extra",
    "resolve_effective_model_request",
    "resolve_provider_primary_wire_api",
]
