"""
Focused runtime-preflight collaborators for ConversationEngine runtime-v2 turns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ai.runtime.usage_metrics import TokenCounter
from app.ai.types import ChatMessage, messages_to_dicts
from app.configs.service import PLATFORM_TENANT_ID
from app.repositories.ai.model_repository import AIModelRepository

from .conversation_helpers import await_if_needed as _await_if_needed


@dataclass
class ConversationRuntimeContext:
    provider: Any
    api_key: Any
    ai_model: Any
    model_code: str
    is_vision: bool
    is_audio: bool
    is_video: bool
    estimated_input: int
    metering_context: Any
    should_meter_usage: bool
    should_record_call_log: bool
    runtime_info: dict[str, Any] = field(default_factory=dict)
    routed_model_id: int | None = None
    route_reason: str | None = None


class ConversationRuntimePreflight:
    """
    Prepare provider/model/quota context for runtime-v2 conversation turns.
    """

    def __init__(self, *, db: Any, gateway: Any) -> None:
        self.db = db
        self.gateway = gateway

    async def prepare(
        self,
        *,
        agent: Any,
        messages: list[ChatMessage],
        tenant_id: int | None,
        route_result: Any | None = None,
        skip_metering_preflight: bool = False,
    ) -> ConversationRuntimeContext:
        (
            ai_model,
            provider_code,
            model_code,
            is_vision,
            is_audio,
            is_video,
        ) = await self._resolve_model_context(
            agent=agent,
            route_result=route_result,
        )
        self._filter_unsupported_attachments(
            messages=messages,
            is_vision=is_vision,
            is_audio=is_audio,
            is_video=is_video,
        )

        provider, api_key = await _await_if_needed(
            self.gateway.get_provider_and_key(
                provider_code,
                tenant_id,
            )
        )

        estimated_input = 0
        metering_context = None
        should_meter_usage = tenant_id is not None and tenant_id > PLATFORM_TENANT_ID
        should_record_call_log = tenant_id is not None
        if should_record_call_log and ai_model:
            estimated_input = TokenCounter.count_messages_tokens(
                messages_to_dicts(messages)
            )
        if should_meter_usage and ai_model and not skip_metering_preflight:
            metering_context = await _await_if_needed(
                self.gateway.usage_recorder.check_rate_and_quota(
                    tenant_id,
                    ai_model.id,
                    ai_model,
                    estimated_input,
                )
            )

        routed_model_id, route_reason = self._resolve_route_metadata(route_result)
        return ConversationRuntimeContext(
            provider=provider,
            api_key=api_key,
            ai_model=ai_model,
            model_code=model_code,
            is_vision=is_vision,
            is_audio=is_audio,
            is_video=is_video,
            estimated_input=estimated_input,
            metering_context=metering_context,
            should_meter_usage=should_meter_usage,
            should_record_call_log=should_record_call_log,
            routed_model_id=routed_model_id,
            route_reason=route_reason,
            runtime_info=self._build_runtime_info(
                provider=provider,
                ai_model=ai_model,
                model_code=model_code,
            ),
        )

    async def _resolve_model_context(
        self,
        *,
        agent: Any,
        route_result: Any | None,
    ) -> tuple[Any, str, str, bool, bool, bool]:
        if route_result is not None and getattr(route_result, "is_overridden", False):
            provider_code = route_result.provider_code or ""
            model_code = route_result.model_code or ""
            routed_model_id = int(getattr(route_result, "model_id", 0) or 0)
            route_model_obj = None
            if routed_model_id:
                route_model_obj = await AIModelRepository(self.db).get_active_with_provider(
                    routed_model_id,
                )
            if route_model_obj is not None:
                return (
                    route_model_obj,
                    provider_code,
                    model_code,
                    bool(route_model_obj.supports_vision),
                    bool(getattr(route_model_obj, "supports_audio", False)),
                    bool(getattr(route_model_obj, "supports_video", False)),
                )
            ai_model = agent.model
            reason_text = str(route_result.reason or "")
            return (
                ai_model,
                provider_code,
                model_code,
                "vision" in reason_text,
                "audio" in reason_text,
                "video" in reason_text,
            )

        model_obj = agent.model
        return (
            model_obj,
            model_obj.provider.code if model_obj and model_obj.provider else "",
            model_obj.code if model_obj else "",
            bool(model_obj.supports_vision) if model_obj else False,
            bool(getattr(model_obj, "supports_audio", False)) if model_obj else False,
            bool(getattr(model_obj, "supports_video", False)) if model_obj else False,
        )

    @staticmethod
    def _filter_unsupported_attachments(
        *,
        messages: list[ChatMessage],
        is_vision: bool,
        is_audio: bool,
        is_video: bool,
    ) -> None:
        for message in messages:
            if not message.attachments:
                continue
            kept = [
                attachment
                for attachment in message.attachments
                if not (
                    (attachment.get("type") == "image" and not is_vision)
                    or (attachment.get("type") == "audio" and not is_audio)
                    or (attachment.get("type") == "video" and not is_video)
                )
            ]
            message.attachments = kept if kept else None

    @staticmethod
    def _resolve_route_metadata(
        route_result: Any | None,
    ) -> tuple[int | None, str | None]:
        if route_result is None or not getattr(route_result, "is_overridden", False):
            return None, None
        routed_model_id = int(getattr(route_result, "model_id", 0) or 0) or None
        route_reason = str(getattr(route_result, "reason", "") or "").strip() or None
        return routed_model_id, route_reason

    @staticmethod
    def _build_runtime_info(
        *,
        provider: Any,
        ai_model: Any,
        model_code: str,
    ) -> dict[str, Any]:
        return {
            "provider_id": provider.id,
            "provider_name": (
                getattr(provider, "name", None)
                or getattr(provider, "code", None)
                or f"Provider #{provider.id}"
            ),
            "model_id": ai_model.id if ai_model else None,
            "model_name": (
                (getattr(ai_model, "name", None) or model_code) if ai_model else None
            ),
            "model_code": model_code,
        }


__all__ = [
    "ConversationRuntimeContext",
    "ConversationRuntimePreflight",
]
