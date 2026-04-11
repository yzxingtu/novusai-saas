"""Call-log and billing helpers used by AIGateway facade."""

from __future__ import annotations

from typing import Any

from app.ai.types import (
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
    ImageGenerationResponse,
    messages_to_dicts,
)
from app.configs.service import PLATFORM_TENANT_ID
from app.core.logging import LogManager
from app.core.runtime_identity import get_runtime_identity_tag
from app.enums.log import UserTypeEnum as LogUserTypeEnum
from app.models.ai import AIModel, AIProvider

logger = LogManager.get_logger("ai")


class GatewayCallLogBridge:
    """Decoupled helpers for request diagnostics and immutable billing snapshots."""

    @staticmethod
    def resolve_call_user_type(
        tenant_id: int | None,
        user_type: str | None = None,
    ) -> str | None:
        if user_type:
            return user_type
        if tenant_id is None:
            return None
        if tenant_id == PLATFORM_TENANT_ID:
            return LogUserTypeEnum.ADMIN.value
        return LogUserTypeEnum.TENANT_ADMIN.value

    @staticmethod
    def build_request_log_data(
        *,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int | None,
        top_p: float,
        tools: list[dict] | None,
        tool_choice: str | None,
        all_tool_names: list[str] | None = None,
        retry_count: int = 0,
        tool_use_policy_family: str | None = None,
        tool_use_policy_mode: str | None = None,
        allowed_tool_names: list[str] | None = None,
        breach_retry_result: str | None = None,
        stream: bool = False,
    ) -> dict[str, object]:
        selected_tool_names = [
            ((tool.get("function", {}) or {}).get("name"))
            for tool in (tools or [])
            if isinstance(tool, dict)
        ]
        selected_tool_names = [name for name in selected_tool_names if name]
        payload: dict[str, object] = {
            "messages": messages_to_dicts(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "tools": tools,
            "tool_choice": tool_choice,
            "runtime_identity": get_runtime_identity_tag(),
            "selected_tool_names": selected_tool_names,
            "all_tool_names": all_tool_names or selected_tool_names,
            "tool_use_policy": {
                "family": tool_use_policy_family or "none",
                "mode": tool_use_policy_mode or ("auto" if tools else "none"),
                "allowed_tool_names": allowed_tool_names or [],
            },
        }
        if stream:
            payload["_stream"] = True
        if retry_count > 0:
            payload["_retry_count"] = retry_count
        if breach_retry_result:
            payload["breach_retry_result"] = breach_retry_result
        return payload

    @staticmethod
    def warn_policy_not_loaded(
        *,
        tools: list[dict] | None,
        tool_choice: str | None,
        conversation_id: int | None,
        agent_id: int | None,
    ) -> None:
        if not tools or tool_choice:
            return
        tool_names = {
            (tool.get("function", {}) or {}).get("name", "")
            for tool in tools
            if isinstance(tool, dict)
        }
        if not ({"web_search", "fetch_url"} & tool_names):
            return
        logger.warning(
            "Tool policy not loaded: status=policy_not_loaded runtime={} conversation_id={} agent_id={} tool_names={}",
            get_runtime_identity_tag(),
            conversation_id,
            agent_id,
            sorted(name for name in tool_names if name),
        )

    @staticmethod
    def resolve_billing_context(
        tenant_id: int | None,
        *,
        user_id: int | None,
        user_type: str | None,
        billing_context: dict | None = None,
    ) -> dict[str, object | None]:
        payload = dict(billing_context or {})
        default_billing_tenant_id = (
            tenant_id
            if tenant_id is not None and tenant_id > PLATFORM_TENANT_ID
            else None
        )
        payload.setdefault("billing_tenant_id", default_billing_tenant_id)
        payload.setdefault("actor_user_id", user_id)
        payload.setdefault("actor_user_type", user_type)
        return payload

    @staticmethod
    def merge_model_provider_snapshots(
        billing_context: dict | None,
        *,
        provider: AIProvider | None,
        ai_model: AIModel | None,
    ) -> dict[str, object | None]:
        merged = dict(billing_context or {})
        if ai_model is not None:
            merged.setdefault(
                "model_name_snapshot",
                getattr(ai_model, "name", None) or getattr(ai_model, "code", None),
            )
        if provider is not None:
            merged.setdefault(
                "provider_name_snapshot",
                getattr(provider, "name", None) or getattr(provider, "code", None),
            )
        return merged

    @staticmethod
    def attach_runtime_metadata(
        payload: ChatResponse | EmbeddingResponse | ImageGenerationResponse,
        *,
        provider: AIProvider,
        ai_model: AIModel,
    ) -> None:
        metadata = dict(getattr(payload, "metadata", {}) or {})
        metadata["runtime_model_info"] = {
            "provider_id": provider.id,
            "provider_name": (
                getattr(provider, "name", None)
                or getattr(provider, "code", None)
                or f"Provider #{provider.id}"
            ),
            "model_id": ai_model.id,
            "model_name": (
                getattr(ai_model, "name", None)
                or getattr(ai_model, "code", None)
                or f"Model #{ai_model.id}"
            ),
            "model_code": getattr(ai_model, "code", None),
        }
        payload.metadata = metadata
