"""
OpenAI Compatible Adapter / OpenAI 兼容适配器

Supports OpenAI official API and all compatible services
(e.g. DeepSeek, Zhipu, Tongyi Qianwen and other domestic LLMs).
支持 OpenAI 官方 API 及所有兼容服务（如 DeepSeek、智谱、通义千问等国产大模型）。
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

import httpx
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI
from openai.types import CreateEmbeddingResponse
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from app.ai.adapters.base import BaseAdapter
from app.ai.exceptions import (
    AIGatewayError,
    ContentFilterError,
    ModelNotFoundError,
    ProviderConnectionError,
    ProviderTimeoutError,
    convert_openai_error,
)
from app.ai.text_semantics import extract_data_url_payload, split_last_suffix
from app.ai.tools.security import SSRFBlockedError, UrlValidator
from app.ai.types import (
    ChatChunk,
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
    ImageGenerationResponse,
    ImageResponse,
)
from app.ai.usage_mode import resolve_chat_usage
from app.ai.utils.chat_attachment_media import resolve_image_url_for_llm
from app.ai.web_search.types import (
    PROVIDER_MODE_NATIVE,
    STATUS_NO_RESULTS,
    STATUS_PARSE_ERROR,
    STATUS_POLICY_FILTERED,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    STATUS_UNSUPPORTED,
    STATUS_UPSTREAM_ERROR,
    SearchProviderRun,
    SearchResultItem,
)
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")


async def _aclose_openai_stream(stream: Any) -> None:
    """Close upstream SDK stream when the wire has sent a terminal SSE event but keeps HTTP open."""
    if stream is None or not hasattr(stream, "aclose"):
        return
    try:
        await stream.aclose()
    except Exception as exc:  # noqa: BLE001
        logger.debug("OpenAI upstream stream aclose (ignored): {}", exc)


_RESPONSES_TOOL_FALLBACK_DISABLED = {"0", "false", "no", "off"}


# Native audio: when True and supports_audio, convert audio attachments to OpenAI input_audio block
# 原生音频：为 True 且 supports_audio 时，将音频附件转为 OpenAI input_audio 块
SUPPORTS_NATIVE_AUDIO: bool = True

# MIME type → OpenAI input_audio format (no magic strings)
# MIME 类型 → OpenAI input_audio format
_AUDIO_MIME_TO_OPENAI_FORMAT: dict[str, str] = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/flac": "flac",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/aac": "m4a",
    "audio/ogg": "ogg",
    "audio/webm": "webm",
    "audio/mpeg3": "mpeg",
    "audio/mpg": "mpeg",
}

# Fetch timeout (seconds) and max size for audio URL → bytes
# 音频 URL 拉取超时（秒）与最大字节数
_AUDIO_FETCH_TIMEOUT_SEC: float = 30.0
_AUDIO_MAX_BYTES: int = 25 * 1024 * 1024  # 25 MB  # 补充说明 / note

_RESPONSES_REASONING_SUMMARY_MODEL_PREFIXES: tuple[str, ...] = (
    "gpt-5",
    "o1",
    "o3",
    "o4",
)
_SUPPORTED_REASONING_EFFORTS: tuple[str, ...] = (
    "none",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
)
_OPENAI_RUNTIME_OVERRIDE_PATHS: dict[str, str] = {
    "responses_reasoning_effort": (
        "runtime_overrides.openai_compatible.responses.reasoning.effort"
    ),
    "chat_completions_reasoning_effort": (
        "runtime_overrides.openai_compatible.chat_completions.reasoning_effort"
    ),
    "legacy_reasoning_effort": "reasoning.effort",
    "legacy_reasoning_effort_flat": "reasoning_effort",
    "legacy_reasoning_effort_camel": "reasoningEffort",
    "legacy_model_code_alias": "legacy_model_code_alias",
}
_NATIVE_WEB_SEARCH_MODEL_PREFIXES: tuple[str, ...] = (
    "gpt-4.1",
    "gpt-4o",
    "gpt-5",
    "o3",
    "o4",
)


class OpenAIAdapter(BaseAdapter):
    """
    OpenAI Compatible Adapter / OpenAI 兼容适配器

    Supports OpenAI official API and all compatible services.
    支持 OpenAI 官方 API 及所有兼容服务。
    """

    def __init__(self, api_key: str, base_url: str | None = None, **kwargs):
        super().__init__(api_key, base_url, **kwargs)

        provider_config = self.config.get("provider_config")
        self.provider_config = (
            provider_config.copy() if isinstance(provider_config, dict) else {}
        )
        self.base_url = self._clean_base_url(base_url)

        # Initialize OpenAI client / 初始化 OpenAI 客户端
        client_kwargs = {"api_key": api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        self.client = AsyncOpenAI(**client_kwargs)
        self.wire_api = self._resolve_wire_api(self.provider_config.get("wire_api"))
        self._chat_completions_v1_retry_client: AsyncOpenAI | Any | None = None
        self._chat_completions_v1_retry_base_url: str | None = None

    def _clean_base_url(self, base_url: str | None) -> str | None:
        cleaned_base_url = str(base_url or "").strip()
        return cleaned_base_url or None

    def _resolve_wire_api(self, wire_api: Any) -> str:
        configured_wire_api = str(wire_api or "").strip()
        if configured_wire_api:
            return self._normalize_wire_api(configured_wire_api)
        return self._normalize_wire_api(None)

    @staticmethod
    def _normalize_wire_api_value(wire_api: Any) -> str:
        value = str(wire_api or "").strip().lower().replace("-", "_")
        if value in {"responses", "response", "responses_api"}:
            return "responses"
        return "chat_completions"

    @staticmethod
    def _normalize_reasoning_effort(value: Any) -> str | None:
        normalized = str(value or "").strip().lower()
        if normalized in _SUPPORTED_REASONING_EFFORTS:
            return normalized
        return None

    @staticmethod
    def _extract_runtime_overrides(model_config: Any) -> dict[str, Any]:
        if not isinstance(model_config, dict):
            return {}
        runtime_overrides = model_config.get("runtime_overrides")
        if isinstance(runtime_overrides, dict):
            return runtime_overrides.copy()
        return {}

    @classmethod
    def _extract_protocol_reasoning_effort_override(
        cls,
        model_config: Any,
        *,
        wire_api: str,
    ) -> tuple[str | None, list[str], dict[str, str]]:
        runtime_overrides = cls._extract_runtime_overrides(model_config)
        openai_overrides = runtime_overrides.get("openai_compatible")
        if not isinstance(openai_overrides, dict):
            return (None, [], {})

        normalized_wire_api = (
            "responses"
            if str(wire_api or "").strip().lower() == "responses"
            else "chat_completions"
        )

        ignored_overrides: list[str] = []
        ignore_reasons: dict[str, str] = {}

        if normalized_wire_api == "responses":
            path = _OPENAI_RUNTIME_OVERRIDE_PATHS["responses_reasoning_effort"]
            responses_overrides = openai_overrides.get("responses")
            if not isinstance(responses_overrides, dict):
                return (None, ignored_overrides, ignore_reasons)
            reasoning = responses_overrides.get("reasoning")
            raw_effort = (
                reasoning.get("effort") if isinstance(reasoning, dict) else None
            )
        else:
            path = _OPENAI_RUNTIME_OVERRIDE_PATHS["chat_completions_reasoning_effort"]
            chat_overrides = openai_overrides.get("chat_completions")
            if not isinstance(chat_overrides, dict):
                return (None, ignored_overrides, ignore_reasons)
            raw_effort = chat_overrides.get("reasoning_effort")

        if raw_effort is None:
            return (None, ignored_overrides, ignore_reasons)

        normalized_effort = cls._normalize_reasoning_effort(raw_effort)
        if normalized_effort is None:
            ignored_overrides.append(path)
            ignore_reasons[path] = "invalid_value"
            return (None, ignored_overrides, ignore_reasons)

        return (normalized_effort, ignored_overrides, ignore_reasons)

    @classmethod
    def _extract_legacy_reasoning_effort_from_model_config(
        cls,
        model_config: Any,
    ) -> str | None:
        if not isinstance(model_config, dict):
            return None

        reasoning = model_config.get("reasoning")
        if isinstance(reasoning, dict):
            effort = cls._normalize_reasoning_effort(reasoning.get("effort"))
            if effort is not None:
                return effort

        return cls._normalize_reasoning_effort(
            model_config.get("reasoning_effort") or model_config.get("reasoningEffort"),
        )

    @classmethod
    def _get_runtime_overrides_for_provider(
        cls,
        model_config: Any,
        provider_type: str,
    ) -> dict[str, Any]:
        if not isinstance(model_config, dict):
            return {}
        runtime_overrides = model_config.get("runtime_overrides")
        if not isinstance(runtime_overrides, dict):
            return {}
        provider_overrides = runtime_overrides.get(provider_type)
        if not isinstance(provider_overrides, dict):
            return {}
        return dict(provider_overrides)

    @classmethod
    def _get_openai_protocol_override(
        cls,
        *,
        model_config: Any,
        wire_api: str | None,
    ) -> tuple[str | None, str | None]:
        provider_overrides = cls._get_runtime_overrides_for_provider(
            model_config,
            "openai_compatible",
        )
        normalized_wire_api = cls._normalize_wire_api_value(wire_api)
        protocol_overrides = provider_overrides.get(normalized_wire_api)
        if not isinstance(protocol_overrides, dict):
            return (None, None)

        if normalized_wire_api == "responses":
            reasoning = protocol_overrides.get("reasoning")
            if not isinstance(reasoning, dict):
                return (None, None)
            return (
                cls._normalize_reasoning_effort(reasoning.get("effort")),
                "runtime_overrides.openai_compatible.responses.reasoning.effort",
            )

        return (
            cls._normalize_reasoning_effort(protocol_overrides.get("reasoning_effort")),
            "runtime_overrides.openai_compatible.chat_completions.reasoning_effort",
        )

    @classmethod
    def _supports_reasoning_effort_model(cls, model: str) -> bool:
        normalized = str(model or "").strip().lower()
        if not normalized:
            return False
        return any(
            normalized.startswith(prefix)
            for prefix in _RESPONSES_REASONING_SUMMARY_MODEL_PREFIXES
        )

    @classmethod
    def _extract_legacy_reasoning_effort_from_model(
        cls,
        model: str,
    ) -> tuple[str, str | None]:
        normalized_model = str(model or "").strip()
        if not normalized_model:
            return ("", None)

        base_model, effort = split_last_suffix(
            normalized_model,
            separator="-",
            allowed_suffixes=("none", "minimal", "low", "medium", "high", "xhigh"),
        )
        if effort is None:
            return (normalized_model, None)

        if not any(
            base_model.lower().startswith(prefix)
            for prefix in _RESPONSES_REASONING_SUMMARY_MODEL_PREFIXES
        ):
            return (normalized_model, None)

        return (base_model, effort)

    @classmethod
    def resolve_effective_model_request(
        cls,
        *,
        model: str,
        model_config: Any = None,
        wire_api: str | None = None,
    ) -> dict[str, Any]:
        logical_model_code = str(model or "").strip()
        normalized_wire_api = cls._normalize_wire_api_value(wire_api)
        effective_request: dict[str, Any] = {
            "logical_model_code": logical_model_code,
            "upstream_model": logical_model_code,
            "reasoning_effort": None,
            "effective_params": {},
            "applied_overrides": [],
            "ignored_overrides": [],
            "ignore_reasons": {},
            "override_source": "model_code",
        }

        config_effort, config_path = cls._get_openai_protocol_override(
            model_config=model_config,
            wire_api=normalized_wire_api,
        )
        if config_path is not None:
            if config_effort is None:
                effective_request["ignored_overrides"].append(config_path)
                effective_request["ignore_reasons"][config_path] = "invalid_value"
            elif not cls._supports_reasoning_effort_model(logical_model_code):
                effective_request["ignored_overrides"].append(config_path)
                effective_request["ignore_reasons"][config_path] = (
                    "unsupported_model_family"
                )
            else:
                effective_request["reasoning_effort"] = config_effort
                effective_request["override_source"] = "runtime_overrides"
                effective_request["applied_overrides"].append(config_path)

        if effective_request["reasoning_effort"] is None:
            legacy_config_effort = (
                cls._extract_legacy_reasoning_effort_from_model_config(model_config)
            )
            if legacy_config_effort is not None:
                legacy_path = "config.reasoning.effort"
                if cls._supports_reasoning_effort_model(logical_model_code):
                    effective_request["reasoning_effort"] = legacy_config_effort
                    effective_request["override_source"] = "legacy_model_config"
                    effective_request["applied_overrides"].append(legacy_path)
                else:
                    effective_request["ignored_overrides"].append(legacy_path)
                    effective_request["ignore_reasons"][legacy_path] = (
                        "unsupported_model_family"
                    )

        upstream_model, legacy_effort = cls._extract_legacy_reasoning_effort_from_model(
            logical_model_code
        )
        if legacy_effort is not None:
            effective_request["upstream_model"] = upstream_model
            if effective_request["reasoning_effort"] is None:
                effective_request["reasoning_effort"] = legacy_effort
                effective_request["override_source"] = "legacy_model_code"
                effective_request["applied_overrides"].append(
                    "legacy_model_code_suffix"
                )

        if effective_request["reasoning_effort"] is not None:
            if normalized_wire_api == "responses":
                effective_request["effective_params"]["reasoning"] = {
                    "effort": effective_request["reasoning_effort"]
                }
            else:
                effective_request["effective_params"]["reasoning_effort"] = (
                    effective_request["reasoning_effort"]
                )

        return effective_request

    def _log_effective_model_request(
        self,
        *,
        effective_request: dict[str, Any],
        wire_api: str,
    ) -> None:
        logger.info(
            "AI model request resolved: provider_type=openai_compatible logical_model_code={} effective_upstream_model={} effective_reasoning_effort={} wire_api={} override_source={} applied_overrides={} ignored_overrides={} ignore_reasons={}",
            effective_request.get("logical_model_code", ""),
            effective_request.get("upstream_model", ""),
            effective_request.get("reasoning_effort", "") or "",
            wire_api,
            effective_request.get("override_source", ""),
            json.dumps(
                effective_request.get("applied_overrides", []), ensure_ascii=False
            ),
            json.dumps(
                effective_request.get("ignored_overrides", []), ensure_ascii=False
            ),
            json.dumps(effective_request.get("ignore_reasons", {}), ensure_ascii=False),
        )

    @staticmethod
    def _augment_request_metadata(
        metadata: dict[str, Any] | None,
        *,
        effective_request: dict[str, Any],
    ) -> dict[str, Any]:
        enriched = dict(metadata or {})
        enriched["logical_model_code"] = effective_request.get("logical_model_code")
        enriched["effective_upstream_model"] = effective_request.get("upstream_model")
        if effective_request.get("reasoning_effort") is not None:
            enriched["effective_reasoning_effort"] = effective_request.get(
                "reasoning_effort"
            )
        enriched["effective_params"] = dict(
            effective_request.get("effective_params", {}) or {}
        )
        enriched["applied_overrides"] = list(
            effective_request.get("applied_overrides", []) or []
        )
        enriched["ignored_overrides"] = list(
            effective_request.get("ignored_overrides", []) or []
        )
        enriched["ignore_reasons"] = dict(
            effective_request.get("ignore_reasons", {}) or {}
        )
        enriched["model_override_source"] = effective_request.get("override_source")
        return enriched

    @classmethod
    def _apply_runtime_reasoning_effort_override(
        cls,
        effective_request: dict[str, Any],
        *,
        reasoning_effort: Any,
        wire_api: str,
    ) -> dict[str, Any]:
        override = cls._normalize_reasoning_effort(reasoning_effort)
        if override is None:
            return effective_request

        marker = "runtime_reasoning_effort_override"
        logical_model_code = str(
            effective_request.get("logical_model_code")
            or effective_request.get("upstream_model")
            or ""
        )
        if not cls._supports_reasoning_effort_model(logical_model_code):
            ignored_overrides = list(effective_request.get("ignored_overrides", []) or [])
            if marker not in ignored_overrides:
                ignored_overrides.append(marker)
            ignore_reasons = dict(effective_request.get("ignore_reasons", {}) or {})
            ignore_reasons[marker] = "unsupported_model_family"
            effective_request["ignored_overrides"] = ignored_overrides
            effective_request["ignore_reasons"] = ignore_reasons
            return effective_request

        effective_request["reasoning_effort"] = override
        effective_request["override_source"] = "runtime_call_override"
        applied_overrides = list(effective_request.get("applied_overrides", []) or [])
        if marker not in applied_overrides:
            applied_overrides.append(marker)
        effective_request["applied_overrides"] = applied_overrides

        normalized_wire_api = cls._normalize_wire_api_value(wire_api)
        effective_params = dict(effective_request.get("effective_params", {}) or {})
        if normalized_wire_api == "responses":
            effective_params["reasoning"] = {"effort": override}
            effective_params.pop("reasoning_effort", None)
        else:
            effective_params["reasoning_effort"] = override
            effective_params.pop("reasoning", None)
        effective_request["effective_params"] = effective_params
        return effective_request

    def _get_effective_base_url(self) -> str:
        return (self.base_url or "https://api.openai.com/v1").rstrip("/")

    def _build_endpoint_url(self, endpoint_path: str) -> str:
        return f"{self._get_effective_base_url()}/{endpoint_path.lstrip('/')}"

    def _chat_endpoint_path(self) -> str:
        return "responses" if self._use_responses_api() else "chat/completions"

    def _looks_like_html_document(self, payload: str) -> bool:
        preview = str(payload or "").lstrip().lower()
        return (
            preview.startswith("<!doctype")
            or preview.startswith("<html")
            or preview.startswith("<head")
            or preview.startswith("<body")
        )

    def _build_chat_completions_v1_retry_base_url(self) -> str | None:
        cleaned_base_url = str(self.base_url or "").strip()
        if not cleaned_base_url:
            return None

        parsed = urlparse(cleaned_base_url)
        if not parsed.scheme or not parsed.netloc:
            return None

        normalized_path = parsed.path.rstrip("/")
        if normalized_path:
            return None

        return parsed._replace(path="/v1", params="", query="", fragment="").geturl()

    def _get_chat_completions_v1_retry_client(self) -> AsyncOpenAI | Any | None:
        retry_base_url = self._build_chat_completions_v1_retry_base_url()
        if not retry_base_url:
            return None

        if (
            self._chat_completions_v1_retry_client is None
            or self._chat_completions_v1_retry_base_url != retry_base_url
        ):
            self._chat_completions_v1_retry_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=retry_base_url,
            )
            self._chat_completions_v1_retry_base_url = retry_base_url
        return self._chat_completions_v1_retry_client

    async def _retry_chat_completions_with_v1_if_needed(
        self,
        *,
        payload: Any,
        request_params: dict[str, Any],
        model: str,
        stream: bool,
    ) -> Any:
        if not (isinstance(payload, str) and self._looks_like_html_document(payload)):
            return payload

        retry_client = self._get_chat_completions_v1_retry_client()
        retry_base_url = self._chat_completions_v1_retry_base_url
        if retry_client is None or not retry_base_url:
            return payload

        logger.warning(
            "chat.completions root endpoint returned HTML; retry with /v1 endpoint: model={} retry_base_url={} stream={}",
            model,
            retry_base_url,
            stream,
        )
        return await retry_client.chat.completions.create(**request_params)

    def _responses_tool_call_fallback_enabled(self) -> bool:
        raw_value = self.provider_config.get("responses_tool_call_fallback_enabled")
        if raw_value is None:
            return True
        if isinstance(raw_value, bool):
            return raw_value
        return str(raw_value).strip().lower() not in _RESPONSES_TOOL_FALLBACK_DISABLED

    @staticmethod
    def _extract_status_code(error: Exception) -> int | None:
        raw_status = getattr(error, "status_code", None)
        if raw_status is None:
            response = getattr(error, "response", None)
            raw_status = getattr(response, "status_code", None)
        try:
            return int(raw_status) if raw_status is not None else None
        except (TypeError, ValueError):
            return None

    def _should_fallback_from_responses_error(
        self,
        error: Exception,
        *,
        tools: list[dict] | None,
        tool_choice: str | None,
        use_responses_api: bool | None = None,
    ) -> bool:
        if not (
            self._use_responses_api()
            if use_responses_api is None
            else bool(use_responses_api)
        ):
            return False
        if not self._responses_tool_call_fallback_enabled():
            return False
        if not tools and not tool_choice:
            return False

        if isinstance(
            error,
            (
                APIConnectionError,
                APITimeoutError,
                httpx.ConnectError,
                httpx.TimeoutException,
            ),
        ):
            return True

        if isinstance(error, AIGatewayError):
            status_code = self._extract_status_code(error)
            return bool(status_code is not None and 500 <= status_code < 600)

        status_code = self._extract_status_code(error)
        return bool(status_code is not None and 500 <= status_code < 600)

    def _log_responses_tool_call_fallback(
        self,
        *,
        model: str,
        stream: bool,
        error: Exception,
    ) -> None:
        logger.warning(
            "Responses tool call failed, fallback to chat.completions: model={} stream={} error_type={} status_code={} error={}",
            model,
            stream,
            type(error).__name__,
            self._extract_status_code(error),
            str(error),
        )

    def _format_preview(self, payload: Any, limit: int = 400) -> str:
        if payload is None:
            return ""
        if isinstance(payload, str):
            text = payload
        else:
            try:
                text = json.dumps(payload, ensure_ascii=False)
            except TypeError:
                text = repr(payload)
        return text[:limit]

    @staticmethod
    def _extract_usage_int(usage: Any, *field_names: str) -> int | None:
        """Extract token counts from SDK objects or dict payloads returned by compatible gateways."""
        if usage is None:
            return None

        for field_name in field_names:
            if isinstance(usage, dict):
                value = usage.get(field_name)
            else:
                value = getattr(usage, field_name, None)
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                logger.debug(
                    "Ignore non-integer usage field {}={!r}", field_name, value
                )
                return None

        return None

    def _extract_usage_tokens(
        self, usage: Any
    ) -> tuple[int | None, int | None, int | None]:
        """Support both Responses-style and Chat Completions-style usage field names."""
        input_tokens = self._extract_usage_int(usage, "input_tokens", "prompt_tokens")
        output_tokens = self._extract_usage_int(
            usage, "output_tokens", "completion_tokens"
        )
        total_tokens = self._extract_usage_int(usage, "total_tokens")
        if total_tokens is None and (
            input_tokens is not None or output_tokens is not None
        ):
            total_tokens = (input_tokens or 0) + (output_tokens or 0)
        return input_tokens, output_tokens, total_tokens

    async def _retrieve_responses_usage(
        self,
        response_id: str | None,
    ) -> tuple[int | None, int | None, int | None]:
        """Fallback: retrieve final response object when stream terminal event omits usage."""
        if not response_id:
            return (None, None, None)
        try:
            response = await self.client.responses.retrieve(response_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Responses usage retrieve failed: response_id={} error={}",
                response_id,
                str(exc),
            )
            return (None, None, None)

        return self._extract_usage_tokens(getattr(response, "usage", None))

    @staticmethod
    def _estimate_responses_stream_usage(
        messages: list[ChatMessage],
        output_text: str,
    ) -> tuple[int, int, int]:
        usage = resolve_chat_usage(
            messages=messages,
            output_text=output_text,
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
        )
        return usage.input_tokens, usage.output_tokens, usage.total_tokens

    def _log_upstream_request(
        self,
        *,
        endpoint_path: str,
        model: str,
        stream: bool,
        wire_api: str | None = None,
    ) -> None:
        logger.info(
            "AI upstream request: wire_api={} method=POST url={} model={} stream={} auth_header=Bearer content_type=application/json accept={}",
            wire_api or self.wire_api,
            self._build_endpoint_url(endpoint_path),
            model,
            stream,
            "text/event-stream" if stream else "application/json",
        )

    def _log_upstream_error(
        self,
        error: Exception,
        *,
        endpoint_path: str,
        model: str,
        wire_api: str | None = None,
    ) -> None:
        response = getattr(error, "response", None)
        request = getattr(response, "request", None)
        request_url = str(
            getattr(request, "url", "") or self._build_endpoint_url(endpoint_path)
        )
        status_code = getattr(error, "status_code", None)
        if status_code is None and response is not None:
            status_code = getattr(response, "status_code", None)
        content_type = None
        if response is not None:
            headers = getattr(response, "headers", None)
            if headers is not None:
                content_type = headers.get("content-type")
        body_preview = self._format_preview(
            getattr(error, "body", None) or getattr(response, "text", None)
        )
        logger.warning(
            "AI upstream error: wire_api={} url={} model={} status_code={} content_type={} response_preview={}",
            wire_api or self.wire_api,
            request_url,
            model,
            status_code,
            content_type or "",
            body_preview,
        )

    def _build_chat_completions_request(
        self,
        *,
        openai_messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int | None,
        top_p: float,
        tools: list[dict] | None,
        tool_choice: str | None,
        stream: bool,
        **kwargs,
    ) -> dict[str, Any]:
        effective_request = kwargs.pop("_effective_model_request", None)
        model_config = kwargs.pop("model_config", None)
        if effective_request is None:
            effective_request = self.resolve_effective_model_request(
                model=model,
                model_config=(
                    model_config
                    if model_config is not None
                    else self.config.get("model_config")
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
        if tools:
            request_params["tools"] = tools
            request_params["tool_choice"] = tool_choice or "auto"
        if kwargs.get(
            "reasoning_effort"
        ) is None and "reasoning_effort" in effective_request.get(
            "effective_params", {}
        ):
            request_params["reasoning_effort"] = effective_request["effective_params"][
                "reasoning_effort"
            ]
        request_params.update(kwargs)
        return request_params

    async def _chat_via_chat_completions(
        self,
        *,
        request_params: dict[str, Any],
        messages: list[ChatMessage],
        model: str,
        fallback_to_responses: bool = True,
        responses_kwargs: dict[str, Any] | None = None,
    ) -> ChatResponse:
        effective_model = str(request_params.get("model") or model)
        self._log_upstream_request(
            endpoint_path="chat/completions",
            model=effective_model,
            stream=False,
            wire_api="chat_completions",
        )
        logger.info(
            "Chat request: model={} messages={}", effective_model, len(messages)
        )
        response = await self.client.chat.completions.create(**request_params)
        response = await self._retry_chat_completions_with_v1_if_needed(
            payload=response,
            request_params=request_params,
            model=effective_model,
            stream=False,
        )

        if fallback_to_responses and self._should_fallback_to_responses(response):
            logger.warning(
                "Chat response missing choices; fallback to responses API: model={} response_type={}",
                model,
                type(response).__name__,
            )
            return await self._chat_via_responses(**(responses_kwargs or {}))

        if self._is_salvageable_raw_text_chat_response(response):
            logger.warning(
                "Chat response returned raw text; coerce to assistant message: model={} response_type={}",
                model,
                type(response).__name__,
            )
            return ChatResponse(
                message=ChatMessage(role="assistant", content=response.strip()),
                model=model,
                finish_reason="stop",
                metadata={
                    "protocol_path": "chat_completions",
                    "response_shape": "raw_text",
                },
            )

        # Reject non-ChatCompletion responses (e.g. HTML/JSON errors) / 拒绝非 ChatCompletion 响应（如 HTML/JSON 错误体）
        if isinstance(response, str):
            logger.error(
                "Chat response returned unsalvageable string payload: model={} preview={}",
                model,
                response[:200],
            )
            raise ValueError(
                f"Upstream returned invalid string response: {response[:100]}"
            )

        return self._convert_chat_response(response, model)

    async def _stream_chat_via_chat_completions(
        self,
        *,
        request_params: dict[str, Any],
        model: str,
        fallback_to_responses: bool = True,
        responses_kwargs: dict[str, Any] | None = None,
    ) -> AsyncIterator[ChatChunk]:
        effective_model = str(request_params.get("model") or model)
        self._log_upstream_request(
            endpoint_path="chat/completions",
            model=effective_model,
            stream=True,
            wire_api="chat_completions",
        )
        logger.info("Stream chat request: model={}", effective_model)
        stream = await self.client.chat.completions.create(**request_params)
        stream = await self._retry_chat_completions_with_v1_if_needed(
            payload=stream,
            request_params=request_params,
            model=effective_model,
            stream=True,
        )
        stream_closed = False

        try:
            first_chunk = await anext(stream, None)
            if first_chunk is None:
                return

            if fallback_to_responses and self._should_fallback_to_responses(
                first_chunk
            ):
                logger.warning(
                    "Stream chunk missing choices; fallback to responses API: model={} chunk_type={}",
                    model,
                    type(first_chunk).__name__,
                )
                await _aclose_openai_stream(stream)
                stream_closed = True
                async for chunk in self._stream_chat_via_responses(
                    **(responses_kwargs or {}),
                ):
                    yield chunk
                return

            first_chat_chunk = self._convert_chat_chunk(first_chunk, model)
            yield first_chat_chunk
            if first_chat_chunk.finish_reason is not None:
                logger.info(
                    "Stream finish_reason on first chunk, closing upstream: model={} finish_reason={} wire_api=chat_completions",
                    model,
                    first_chat_chunk.finish_reason,
                )
                return

            async for chunk in stream:
                chat_chunk = self._convert_chat_chunk(chunk, model)
                yield chat_chunk
                if chat_chunk.finish_reason is not None:
                    logger.info(
                        "Stream finish_reason received, closing upstream: model={} finish_reason={} wire_api=chat_completions",
                        model,
                        chat_chunk.finish_reason,
                    )
                    break
        finally:
            if not stream_closed:
                await _aclose_openai_stream(stream)

    def _chat_response_to_stream_chunk(self, response: ChatResponse) -> ChatChunk:
        """Convert a sync chat response into a terminal stream chunk / 将同步响应转换为终止流式块。"""
        finish_reason = response.finish_reason
        if not finish_reason:
            finish_reason = (
                "tool_calls"
                if (response.tool_calls or response.message.tool_calls)
                else "stop"
            )
        return ChatChunk(
            delta=response.message.content or "",
            reasoning_delta=response.message.reasoning_content or "",
            role=response.message.role,
            finish_reason=finish_reason,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
            tool_calls=response.tool_calls or response.message.tool_calls,
            metadata=dict(response.metadata or {}),
        )

    async def _stream_chat_completions_with_sync_rescue(
        self,
        *,
        request_params: dict[str, Any],
        sync_request_params: dict[str, Any],
        messages: list[ChatMessage],
        model: str,
        rescue_reason: str,
    ) -> AsyncIterator[ChatChunk]:
        """
        Stream via chat.completions and rescue empty / broken streams with sync chat.
        使用 chat.completions 流式输出，并在空流或首块前异常时回退到同步 chat。
        """
        emitted_meaningful_chunk = False
        stream_error: Exception | None = None

        try:
            async for chunk in self._stream_chat_via_chat_completions(
                request_params=request_params,
                model=model,
                fallback_to_responses=False,
            ):
                if self._is_meaningful_stream_chunk(chunk):
                    emitted_meaningful_chunk = True
                yield chunk
        except Exception as exc:  # noqa: BLE001
            if emitted_meaningful_chunk:
                raise
            stream_error = exc

        if emitted_meaningful_chunk:
            return

        logger.warning(
            "chat.completions stream had no meaningful chunk, rescue with sync chat: model={} reason={} stream_error_type={} stream_error={}",
            model,
            rescue_reason,
            type(stream_error).__name__ if stream_error is not None else "",
            str(stream_error) if stream_error is not None else "",
        )
        try:
            response = await self._chat_via_chat_completions(
                request_params=sync_request_params,
                messages=messages,
                model=model,
                fallback_to_responses=False,
            )
            yield self._chat_response_to_stream_chunk(response)
        except Exception as rescue_error:
            logger.error(
                "Sync rescue failed after stream failure: model={} stream_error={} rescue_error={}",
                model,
                str(stream_error) if stream_error is not None else "None",
                str(rescue_error),
            )
            # Re-raise original stream error if present, else rescue error / 优先抛出原始流错误，否则抛出 rescue 异常
            raise stream_error if stream_error is not None else rescue_error

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        stream: bool = False,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> ChatResponse:
        """
        Chat conversation (synchronous mode) / 聊天对话（同步模式）
        """
        _ = stream
        active_endpoint_path = (
            "responses" if self._use_responses_api() else "chat/completions"
        )
        active_wire_api = (
            "responses" if self._use_responses_api() else "chat_completions"
        )
        effective_error_model = model
        try:
            runtime_force_wire_api = kwargs.pop("_runtime_force_wire_api", None)
            runtime_disable_cross_protocol_fallback = bool(
                kwargs.pop("_runtime_disable_cross_protocol_fallback", False),
            )
            runtime_reasoning_effort_override = kwargs.pop(
                "_runtime_reasoning_effort_override",
                None,
            )
            runtime_model_config = kwargs.pop("model_config", None)
            if runtime_model_config is None:
                runtime_model_config = self.config.get("model_config")
            runtime_wire_api = self._resolve_runtime_wire_api(runtime_force_wire_api)
            use_responses_api = runtime_wire_api == "responses"
            active_endpoint_path = (
                "responses" if use_responses_api else "chat/completions"
            )
            active_wire_api = "responses" if use_responses_api else "chat_completions"
            effective_request = self.resolve_effective_model_request(
                model=model,
                model_config=runtime_model_config,
                wire_api=active_wire_api,
            )
            effective_request = self._apply_runtime_reasoning_effort_override(
                effective_request,
                reasoning_effort=runtime_reasoning_effort_override,
                wire_api=active_wire_api,
            )
            self._log_effective_model_request(
                effective_request=effective_request,
                wire_api=active_wire_api,
            )
            effective_error_model = str(
                effective_request.get("upstream_model") or model
            )

            # Pop adapter-only flags before building request params / 提取适配器专用标志，避免传入 API
            vision_flag = kwargs.pop("supports_vision", True)
            audio_flag = kwargs.pop("supports_audio", False)
            video_flag = kwargs.pop("supports_video", False)

            # Convert message format / 转换消息格式
            openai_messages = await self._convert_messages(
                messages,
                supports_vision=vision_flag,
                supports_audio=audio_flag,
                supports_video=video_flag,
            )

            request_params = self._build_chat_completions_request(
                openai_messages=openai_messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                tools=tools,
                tool_choice=tool_choice,
                stream=False,
                model_config=runtime_model_config,
                _effective_model_request=effective_request,
                **kwargs,
            )
            responses_kwargs = {
                "messages": messages,
                "model": model,
                "model_config": runtime_model_config,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "tools": tools,
                "tool_choice": tool_choice,
                "supports_vision": vision_flag,
                "supports_audio": audio_flag,
                "supports_video": video_flag,
                "_effective_model_request": effective_request,
                **kwargs,
            }

            if use_responses_api:
                try:
                    response = await self._chat_via_responses(**responses_kwargs)
                except Exception as responses_error:
                    if (
                        not runtime_disable_cross_protocol_fallback
                        and self._should_fallback_from_responses_error(
                            responses_error,
                            tools=tools,
                            tool_choice=tool_choice,
                            use_responses_api=use_responses_api,
                        )
                    ):
                        self._log_responses_tool_call_fallback(
                            model=model,
                            stream=False,
                            error=responses_error,
                        )
                        active_endpoint_path = "chat/completions"
                        active_wire_api = "chat_completions"
                        response = await self._chat_via_chat_completions(
                            request_params=request_params,
                            messages=messages,
                            model=model,
                            fallback_to_responses=False,
                        )
                    else:
                        raise
            else:
                response = await self._chat_via_chat_completions(
                    request_params=request_params,
                    messages=messages,
                    model=model,
                    fallback_to_responses=not runtime_disable_cross_protocol_fallback,
                    responses_kwargs=(
                        responses_kwargs
                        if not runtime_disable_cross_protocol_fallback
                        else None
                    ),
                )

            response.metadata = dict(response.metadata or {})
            response.metadata.setdefault("protocol_path", active_wire_api)
            response.metadata = self._augment_request_metadata(
                response.metadata,
                effective_request=effective_request,
            )
            return response

        except AIGatewayError:
            raise
        except Exception as e:
            self._log_upstream_error(
                e,
                endpoint_path=active_endpoint_path,
                model=effective_error_model,
                wire_api=active_wire_api,
            )
            logger.error("Chat error: model={} error={}", model, str(e))
            raise convert_openai_error(
                e, provider_code="openai", model_code=model
            ) from e

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> AsyncIterator[ChatChunk]:
        """
        Chat conversation (streaming mode) / 聊天对话（流式模式）
        """
        active_endpoint_path = (
            "responses" if self._use_responses_api() else "chat/completions"
        )
        active_wire_api = (
            "responses" if self._use_responses_api() else "chat_completions"
        )
        effective_error_model = model
        try:
            runtime_force_wire_api = kwargs.pop("_runtime_force_wire_api", None)
            runtime_disable_cross_protocol_fallback = bool(
                kwargs.pop("_runtime_disable_cross_protocol_fallback", False),
            )
            runtime_reasoning_effort_override = kwargs.pop(
                "_runtime_reasoning_effort_override",
                None,
            )
            runtime_model_config = kwargs.pop("model_config", None)
            if runtime_model_config is None:
                runtime_model_config = self.config.get("model_config")
            runtime_wire_api = self._resolve_runtime_wire_api(runtime_force_wire_api)
            use_responses_api = runtime_wire_api == "responses"
            active_endpoint_path = (
                "responses" if use_responses_api else "chat/completions"
            )
            active_wire_api = "responses" if use_responses_api else "chat_completions"
            effective_request = self.resolve_effective_model_request(
                model=model,
                model_config=runtime_model_config,
                wire_api=active_wire_api,
            )
            effective_request = self._apply_runtime_reasoning_effort_override(
                effective_request,
                reasoning_effort=runtime_reasoning_effort_override,
                wire_api=active_wire_api,
            )
            self._log_effective_model_request(
                effective_request=effective_request,
                wire_api=active_wire_api,
            )
            effective_error_model = str(
                effective_request.get("upstream_model") or model
            )

            # Pop adapter-only flags before building request params / 提取适配器专用标志，避免传入 API
            vision_flag = kwargs.pop("supports_vision", True)
            audio_flag = kwargs.pop("supports_audio", False)
            video_flag = kwargs.pop("supports_video", False)

            # Convert message format / 转换消息格式
            openai_messages = await self._convert_messages(
                messages,
                supports_vision=vision_flag,
                supports_audio=audio_flag,
                supports_video=video_flag,
            )

            request_params = self._build_chat_completions_request(
                openai_messages=openai_messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                tools=tools,
                tool_choice=tool_choice,
                stream=True,
                model_config=runtime_model_config,
                _effective_model_request=effective_request,
                **kwargs,
            )
            sync_request_params = self._build_chat_completions_request(
                openai_messages=openai_messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                tools=tools,
                tool_choice=tool_choice,
                stream=False,
                model_config=runtime_model_config,
                _effective_model_request=effective_request,
                **kwargs,
            )
            responses_kwargs = {
                "messages": messages,
                "model": model,
                "model_config": runtime_model_config,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "tools": tools,
                "tool_choice": tool_choice,
                "supports_vision": vision_flag,
                "supports_audio": audio_flag,
                "supports_video": video_flag,
                "_effective_model_request": effective_request,
                **kwargs,
            }

            if use_responses_api:
                responses_stream_emitted_meaningful_chunk = False
                try:
                    async for chunk in self._stream_chat_via_responses(
                        **responses_kwargs,
                    ):
                        if self._is_meaningful_stream_chunk(chunk):
                            responses_stream_emitted_meaningful_chunk = True
                        chunk.metadata = self._augment_request_metadata(
                            getattr(chunk, "metadata", None),
                            effective_request=effective_request,
                        )
                        yield chunk
                    return
                except Exception as responses_error:
                    if (
                        not responses_stream_emitted_meaningful_chunk
                        and not runtime_disable_cross_protocol_fallback
                        and self._should_fallback_from_responses_error(
                            responses_error,
                            tools=tools,
                            tool_choice=tool_choice,
                            use_responses_api=use_responses_api,
                        )
                    ):
                        self._log_responses_tool_call_fallback(
                            model=model,
                            stream=True,
                            error=responses_error,
                        )
                        active_endpoint_path = "chat/completions"
                        active_wire_api = "chat_completions"
                        async for (
                            chunk
                        ) in self._stream_chat_completions_with_sync_rescue(
                            request_params=request_params,
                            sync_request_params=sync_request_params,
                            messages=messages,
                            model=model,
                            rescue_reason="responses_fallback",
                        ):
                            chunk.metadata = self._augment_request_metadata(
                                getattr(chunk, "metadata", None),
                                effective_request=effective_request,
                            )
                            yield chunk
                        return
                    if responses_stream_emitted_meaningful_chunk:
                        logger.warning(
                            "Responses stream failed after meaningful chunk; skip cross-protocol fallback: model={} error_type={} error={}",
                            model,
                            type(responses_error).__name__,
                            str(responses_error),
                        )
                    raise

            async for chunk in self._stream_chat_completions_with_sync_rescue(
                request_params=request_params,
                sync_request_params=sync_request_params,
                messages=messages,
                model=model,
                rescue_reason="chat_completions_primary",
            ):
                chunk.metadata = self._augment_request_metadata(
                    getattr(chunk, "metadata", None),
                    effective_request=effective_request,
                )
                yield chunk

        except AIGatewayError:
            raise
        except Exception as e:
            self._log_upstream_error(
                e,
                endpoint_path=active_endpoint_path,
                model=effective_error_model,
                wire_api=active_wire_api,
            )
            logger.error("Stream chat error: model={} error={}", model, str(e))
            raise convert_openai_error(
                e, provider_code="openai", model_code=model
            ) from e

    async def embedding(
        self, texts: list[str], model: str, **kwargs
    ) -> EmbeddingResponse:
        """
        Text embedding / 文本嵌入
        """
        try:
            # Call API / 调用 API
            self._log_upstream_request(
                endpoint_path="embeddings", model=model, stream=False
            )
            logger.info("Embedding request: model={} texts={}", model, len(texts))
            response: CreateEmbeddingResponse = await self.client.embeddings.create(
                input=texts, model=model, **kwargs
            )

            # Convert response / 转换响应
            input_tokens, _, total_tokens = self._extract_usage_tokens(response.usage)
            return EmbeddingResponse(
                embeddings=[item.embedding for item in response.data],
                input_tokens=input_tokens,
                total_tokens=total_tokens,
                model=model,
            )

        except AIGatewayError:
            raise
        except Exception as e:
            self._log_upstream_error(e, endpoint_path="embeddings", model=model)
            logger.error("Embedding error: model={} error={}", model, str(e))
            raise convert_openai_error(
                e, provider_code="openai", model_code=model
            ) from e

    async def list_models(self) -> list[dict]:
        """
        List available models for the provider / 列出供应商可用的模型列表

        Fetches available models via OpenAI /models API.
        通过 OpenAI /models API 获取可用模型。

        Returns:
            Model info list / 模型信息列表
        """
        try:
            self._log_upstream_request(endpoint_path="models", model="", stream=False)
            response = await self.client.models.list()
            return [
                {
                    "id": model.id,
                    "owned_by": getattr(model, "owned_by", None),
                }
                for model in response.data
            ]
        except Exception as e:
            self._log_upstream_error(e, endpoint_path="models", model="")
            logger.error("List models error: {}", str(e))
            raise convert_openai_error(e, provider_code="openai", model_code="") from e

    def _normalize_wire_api(self, wire_api: Any) -> str:
        return self._normalize_wire_api_value(wire_api)

    def _resolve_runtime_wire_api(self, runtime_force_wire_api: Any) -> str:
        if runtime_force_wire_api is None:
            return self.wire_api
        return self._normalize_wire_api(runtime_force_wire_api)

    @staticmethod
    def _is_meaningful_stream_chunk(chunk: ChatChunk) -> bool:
        if chunk is None:
            return False
        if str(getattr(chunk, "delta", "") or "").strip():
            return True
        if str(getattr(chunk, "reasoning_delta", "") or "").strip():
            return True
        return bool(getattr(chunk, "tool_calls", None))

    def _use_responses_api(self) -> bool:
        return self.wire_api == "responses"

    @staticmethod
    def _native_web_search_field(value: Any, name: str) -> Any:
        if isinstance(value, dict):
            return value.get(name)
        return getattr(value, name, None)

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _supports_native_web_search_model(cls, model: str) -> bool:
        normalized = str(model or "").strip().lower()
        if not normalized:
            return False
        return any(
            normalized.startswith(prefix)
            for prefix in _NATIVE_WEB_SEARCH_MODEL_PREFIXES
        )

    @staticmethod
    def _is_verifiable_native_web_search_url(url: str) -> bool:
        parsed = urlparse(str(url or "").strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def _normalize_native_web_search_snippet(
        text: str,
        *,
        title: str,
        start_index: int | None,
        end_index: int | None,
        limit: int = 240,
    ) -> str:
        source_text = str(text or "")
        if start_index is not None and end_index is not None and end_index > start_index:
            left = max(0, start_index - 100)
            right = min(len(source_text), end_index + 120)
            source_text = source_text[left:right]
        normalized = " ".join(source_text.split())
        normalized_title = " ".join(str(title or "").split())
        if normalized_title and normalized.startswith(normalized_title):
            normalized = normalized[len(normalized_title) :].strip(" -:;,")
        if len(normalized) > limit:
            normalized = normalized[:limit].rstrip() + "..."
        return normalized

    def _extract_native_web_search_items(
        self,
        response: Any,
        *,
        provider_label: str,
        backend_key: str,
        max_results: int,
    ) -> tuple[list[SearchResultItem], bool]:
        items: list[SearchResultItem] = []
        seen_urls: set[str] = set()
        saw_unverifiable_url = False

        for item in self._native_web_search_field(response, "output") or []:
            if self._native_web_search_field(item, "type") != "message":
                continue
            for content in self._native_web_search_field(item, "content") or []:
                if self._native_web_search_field(content, "type") != "output_text":
                    continue
                text = str(self._native_web_search_field(content, "text") or "")
                for annotation in (
                    self._native_web_search_field(content, "annotations") or []
                ):
                    if self._native_web_search_field(annotation, "type") != "url_citation":
                        continue
                    url = str(self._native_web_search_field(annotation, "url") or "").strip()
                    if not self._is_verifiable_native_web_search_url(url):
                        saw_unverifiable_url = True
                        continue
                    if url in seen_urls:
                        continue
                    title = (
                        str(self._native_web_search_field(annotation, "title") or "").strip()
                        or url
                    )
                    snippet = self._normalize_native_web_search_snippet(
                        text,
                        title=title,
                        start_index=self._coerce_int(
                            self._native_web_search_field(annotation, "start_index")
                        ),
                        end_index=self._coerce_int(
                            self._native_web_search_field(annotation, "end_index")
                        ),
                    )
                    items.append(
                        SearchResultItem(
                            title=title,
                            url=url,
                            snippet=snippet,
                            source=backend_key,
                            provider=provider_label,
                            provider_mode=PROVIDER_MODE_NATIVE,
                            rank=len(items) + 1,
                        )
                    )
                    seen_urls.add(url)
                    if len(items) >= max_results:
                        return items, saw_unverifiable_url

        for item in self._native_web_search_field(response, "output") or []:
            if self._native_web_search_field(item, "type") != "web_search_call":
                continue
            action = self._native_web_search_field(item, "action")
            for source in self._native_web_search_field(action, "sources") or []:
                url = str(self._native_web_search_field(source, "url") or "").strip()
                if not self._is_verifiable_native_web_search_url(url):
                    saw_unverifiable_url = True
                    continue
                if url in seen_urls:
                    continue
                title = (urlparse(url).netloc or url).strip()
                items.append(
                    SearchResultItem(
                        title=title,
                        url=url,
                        snippet="",
                        source=backend_key,
                        provider=provider_label,
                        provider_mode=PROVIDER_MODE_NATIVE,
                        rank=len(items) + 1,
                    )
                )
                seen_urls.add(url)
                if len(items) >= max_results:
                    return items, saw_unverifiable_url

        return items, saw_unverifiable_url

    def _extract_native_web_search_usage(self, response: Any) -> tuple[int, int, int]:
        usage = self._native_web_search_field(response, "usage")
        input_tokens = self._coerce_int(
            self._native_web_search_field(usage, "input_tokens")
        ) or 0
        output_tokens = self._coerce_int(
            self._native_web_search_field(usage, "output_tokens")
        ) or 0
        total_tokens = self._coerce_int(
            self._native_web_search_field(usage, "total_tokens")
        )
        if total_tokens is None:
            total_tokens = input_tokens + output_tokens
        return input_tokens, output_tokens, total_tokens

    def _extract_native_web_search_request_count(self, response: Any) -> int:
        tool_usage = self._native_web_search_field(response, "tool_usage")
        web_search_usage = self._native_web_search_field(tool_usage, "web_search")
        request_count = self._coerce_int(
            self._native_web_search_field(web_search_usage, "num_requests")
        )
        return int(request_count or 0)

    @staticmethod
    def _extract_urls_from_native_web_search_text(text: str) -> list[tuple[str, int, int]]:
        matches: list[tuple[str, int, int]] = []
        source_text = str(text or "")
        if not source_text:
            return matches
        for match in re.finditer(r"https?://[^\s<>\]\)\"']+", source_text):
            url = str(match.group(0) or "").rstrip(".,;:!?)]")
            if not url:
                continue
            matches.append((url, match.start(), match.start() + len(url)))
        return matches

    async def _native_web_search_via_stream(
        self,
        *,
        query: str,
        max_results: int,
        locale: str | None,
        timeout_seconds: int,
        model: str,
        provider_label: str,
        backend_key: str,
        instructions: str,
    ) -> SearchProviderRun | None:
        collected_text_parts: list[str] = []
        response_usage: Any = None
        saw_web_search_call = False

        try:
            stream = await self.client.responses.create(
                model=model,
                input=query,
                instructions=instructions,
                tools=[
                    {
                        "type": "web_search",
                        "search_context_size": "medium",
                    }
                ],
                tool_choice="required",
                stream=True,
                timeout=float(timeout_seconds),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Native web search stream fallback request failed: provider={} model={} error={}",
                provider_label,
                model,
                str(exc),
            )
            return None

        try:
            async for event in stream:
                event_type = getattr(event, "type", "") or ""
                if event_type.startswith("response.web_search_call"):
                    saw_web_search_call = True
                    continue

                if event_type == "response.output_text.delta":
                    delta = getattr(event, "delta", "") or ""
                    if delta:
                        collected_text_parts.append(delta)
                    continue

                if event_type == "response.output_text.done":
                    text = getattr(event, "text", "") or ""
                    if text and not collected_text_parts:
                        collected_text_parts.append(text)
                    response_usage = getattr(event, "usage", None) or response_usage
                    continue

                if event_type == "response.output_item.done":
                    item = getattr(event, "item", None)
                    item_type = self._native_web_search_field(item, "type")
                    if item_type == "web_search_call":
                        saw_web_search_call = True
                        continue
                    if item_type != "message":
                        continue
                    for content in self._native_web_search_field(item, "content") or []:
                        if self._native_web_search_field(content, "type") != "output_text":
                            continue
                        text = str(self._native_web_search_field(content, "text") or "")
                        if text and not collected_text_parts:
                            collected_text_parts.append(text)
                    continue

                if event_type == "response.completed":
                    response = getattr(event, "response", None)
                    response_usage = (
                        self._native_web_search_field(response, "usage") or response_usage
                    )
                    if response is not None and not collected_text_parts:
                        final_text = self._extract_responses_text(response)
                        if final_text:
                            collected_text_parts.append(final_text)
                    continue
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Native web search stream fallback consumption failed: provider={} model={} error={}",
                provider_label,
                model,
                str(exc),
            )
            return None
        finally:
            await _aclose_openai_stream(stream)

        if not saw_web_search_call:
            return None

        final_text = "".join(collected_text_parts).strip()
        if not final_text:
            input_tokens, output_tokens, total_tokens = self._extract_native_web_search_usage(
                SimpleNamespace(usage=response_usage)
            )
            return SearchProviderRun(
                provider=provider_label,
                provider_mode=PROVIDER_MODE_NATIVE,
                backend_key=backend_key,
                status=STATUS_NO_RESULTS,
                items=[],
                failure_reason="native web search stream returned no candidate sources",
                attempted_backends=[backend_key],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            )

        items: list[SearchResultItem] = []
        seen_urls: set[str] = set()
        saw_unverifiable_url = False
        for url, start_index, end_index in self._extract_urls_from_native_web_search_text(
            final_text
        ):
            if not self._is_verifiable_native_web_search_url(url):
                saw_unverifiable_url = True
                continue
            if url in seen_urls:
                continue
            title = (urlparse(url).netloc or url).strip() or url
            snippet = self._normalize_native_web_search_snippet(
                final_text,
                title=title,
                start_index=start_index,
                end_index=end_index,
            )
            items.append(
                SearchResultItem(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source=backend_key,
                    provider=provider_label,
                    provider_mode=PROVIDER_MODE_NATIVE,
                    rank=len(items) + 1,
                )
            )
            seen_urls.add(url)
            if len(items) >= max_results:
                break

        input_tokens, output_tokens, total_tokens = self._extract_native_web_search_usage(
            SimpleNamespace(usage=response_usage)
        )
        if items:
            return SearchProviderRun(
                provider=provider_label,
                provider_mode=PROVIDER_MODE_NATIVE,
                backend_key=backend_key,
                status=STATUS_SUCCESS,
                items=items,
                attempted_backends=[backend_key],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            )
        if saw_unverifiable_url:
            return SearchProviderRun(
                provider=provider_label,
                provider_mode=PROVIDER_MODE_NATIVE,
                backend_key=backend_key,
                status=STATUS_PARSE_ERROR,
                items=[],
                failure_reason="native web search stream returned no verifiable absolute URLs",
                attempted_backends=[backend_key],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            )
        return SearchProviderRun(
            provider=provider_label,
            provider_mode=PROVIDER_MODE_NATIVE,
            backend_key=backend_key,
            status=STATUS_NO_RESULTS,
            items=[],
            failure_reason="native web search stream returned no candidate sources",
            attempted_backends=[backend_key],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

    def _map_native_web_search_error(self, error: Exception) -> str:
        if isinstance(error, (APITimeoutError, ProviderTimeoutError)):
            return STATUS_TIMEOUT
        if isinstance(error, ContentFilterError):
            return STATUS_POLICY_FILTERED
        if isinstance(error, ModelNotFoundError):
            return STATUS_UNSUPPORTED
        if isinstance(error, ProviderConnectionError):
            return STATUS_UPSTREAM_ERROR

        status_code = self._extract_status_code(error)
        message = str(error).lower()
        if (
            "unsupported" in message
            or "not support" in message
            or "unknown parameter" in message
            or "invalid tool" in message
            or ("web_search" in message and "available" in message)
        ):
            return STATUS_UNSUPPORTED
        if (
            "content_filter" in message
            or "content policy" in message
            or "safety" in message
            or "policy" in message
        ):
            return STATUS_POLICY_FILTERED
        if status_code in {400, 404}:
            return STATUS_UNSUPPORTED
        if status_code == 408:
            return STATUS_TIMEOUT
        return STATUS_UPSTREAM_ERROR

    def supports_native_web_search(self, model: str) -> bool:
        return self._use_responses_api() and self._supports_native_web_search_model(
            model
        )

    async def native_web_search(
        self,
        *,
        query: str,
        max_results: int,
        locale: str | None,
        timeout_seconds: int,
        model: str | None = None,
        provider_label: str | None = None,
        backend_key: str | None = None,
    ) -> SearchProviderRun:
        effective_model = str(model or "").strip()
        effective_provider = str(provider_label or "openai_compatible")
        effective_backend_key = backend_key or f"native:{effective_provider}:{effective_model}"
        if not self.supports_native_web_search(effective_model):
            return SearchProviderRun(
                provider=effective_provider,
                provider_mode=PROVIDER_MODE_NATIVE,
                backend_key=effective_backend_key,
                status=STATUS_UNSUPPORTED,
                items=[],
                failure_reason="responses api or model family does not support native web search",
                attempted_backends=[effective_backend_key],
            )

        return await self._native_web_search_via_responses(
                query=query,
                max_results=max_results,
                locale=locale,
                timeout_seconds=timeout_seconds,
                model=effective_model,
                provider_label=effective_provider,
                backend_key=effective_backend_key,
            )

    async def _native_web_search_via_responses(
        self,
        *,
        query: str,
        max_results: int,
        locale: str | None,
        timeout_seconds: int,
        model: str,
        provider_label: str,
        backend_key: str,
    ) -> SearchProviderRun:
        """Native web search via OpenAI Responses API (hosted web_search tool)."""
        effective_model = model
        effective_provider = provider_label
        effective_backend_key = backend_key
        instructions = (
            "Use hosted web search to find candidate source URLs for the user query. "
            "Return only candidate sources with brief snippets. Do not synthesize facts "
            "or claim conclusions. Every result must be backed by a verifiable absolute "
            "http or https URL that can later be fetched."
        )
        if locale:
            instructions += f" Prefer sources suitable for locale {locale} when relevant."

        try:
            self._log_upstream_request(
                endpoint_path="responses",
                model=effective_model,
                stream=False,
                wire_api="responses",
            )
            response = await self.client.responses.create(
                model=effective_model,
                input=query,
                instructions=instructions,
                tools=[
                    {
                        "type": "web_search",
                        "search_context_size": "medium",
                    }
                ],
                tool_choice="required",
                include=["web_search_call.action.sources"],
                timeout=float(timeout_seconds),
            )
            input_tokens, output_tokens, total_tokens = (
                self._extract_native_web_search_usage(response)
            )
            request_count = self._extract_native_web_search_request_count(response)
            items, saw_unverifiable_url = self._extract_native_web_search_items(
                response,
                provider_label=effective_provider,
                backend_key=effective_backend_key,
                max_results=max_results,
            )
            if items:
                return SearchProviderRun(
                    provider=effective_provider,
                    provider_mode=PROVIDER_MODE_NATIVE,
                    backend_key=effective_backend_key,
                    status=STATUS_SUCCESS,
                    items=items,
                    attempted_backends=[effective_backend_key],
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                )
            if saw_unverifiable_url:
                return SearchProviderRun(
                    provider=effective_provider,
                    provider_mode=PROVIDER_MODE_NATIVE,
                    backend_key=effective_backend_key,
                    status=STATUS_PARSE_ERROR,
                    items=[],
                    failure_reason="native web search returned no verifiable absolute URLs",
                    attempted_backends=[effective_backend_key],
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                )
            if request_count <= 0:
                stream_fallback_run = await self._native_web_search_via_stream(
                    query=query,
                    max_results=max_results,
                    locale=locale,
                    timeout_seconds=timeout_seconds,
                    model=effective_model,
                    provider_label=effective_provider,
                    backend_key=effective_backend_key,
                    instructions=instructions,
                )
                if stream_fallback_run is not None:
                    return stream_fallback_run
                return SearchProviderRun(
                    provider=effective_provider,
                    provider_mode=PROVIDER_MODE_NATIVE,
                    backend_key=effective_backend_key,
                    status=STATUS_UNSUPPORTED,
                    items=[],
                    failure_reason=(
                        "provider responses runtime accepted native web search request "
                        "but did not execute hosted web_search"
                    ),
                    attempted_backends=[effective_backend_key],
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                )
            return SearchProviderRun(
                provider=effective_provider,
                provider_mode=PROVIDER_MODE_NATIVE,
                backend_key=effective_backend_key,
                status=STATUS_NO_RESULTS,
                items=[],
                failure_reason="native web search returned no candidate sources",
                attempted_backends=[effective_backend_key],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            )
        except Exception as exc:
            self._log_upstream_error(
                exc,
                endpoint_path="responses",
                model=effective_model,
                wire_api="responses",
            )
            converted = exc if isinstance(exc, AIGatewayError) else convert_openai_error(
                exc,
                provider_code="openai",
                model_code=effective_model,
            )
            return SearchProviderRun(
                provider=effective_provider,
                provider_mode=PROVIDER_MODE_NATIVE,
                backend_key=effective_backend_key,
                status=self._map_native_web_search_error(exc),
                items=[],
                failure_reason=str(converted),
                attempted_backends=[effective_backend_key],
            )

    def _payload_looks_like_api_error(self, payload: Any) -> bool:
        """True when upstream returned an error object, not a misrouted success body."""
        if payload is None:
            return False
        if getattr(payload, "error", None) is not None:
            return True
        return isinstance(payload, dict) and payload.get("error") is not None

    def _payload_resembles_responses_api_body(self, payload: Any) -> bool:
        """
        True when payload looks like OpenAI Responses API JSON, not arbitrary missing choices.
        仅在响应体像 Responses 结构时才 fallback，避免对 HTML/空对象等误触发二次请求。
        """
        if payload is None:
            return False
        if getattr(payload, "object", None) == "response":
            return True
        if isinstance(payload, dict) and payload.get("object") == "response":
            return True
        if hasattr(payload, "output"):
            return True
        if isinstance(payload, dict) and "output" in payload:
            return True
        if hasattr(payload, "output_text"):
            return True
        return isinstance(payload, dict) and "output_text" in payload

    def _should_fallback_to_responses(self, payload: Any) -> bool:
        if self._use_responses_api():
            return False
        if hasattr(payload, "choices"):
            return False
        if self._payload_looks_like_api_error(payload):
            return False
        return self._payload_resembles_responses_api_body(payload)

    def _is_salvageable_raw_text_chat_response(self, payload: Any) -> bool:
        """
        Accept plain assistant text from compatible gateways, but reject HTML/JSON junk.
        / 接受兼容网关直接返回的纯文本答复，但拒绝 HTML/JSON 垃圾载荷。
        """
        if not isinstance(payload, str):
            return False

        text = payload.strip()
        if not text:
            return False

        lowered = text.lower()
        if (
            lowered.startswith("<!doctype")
            or lowered.startswith("<html")
            or lowered.startswith("<body")
        ):
            return False
        if text.startswith("<"):
            return False
        return not (text.startswith("{") or text.startswith("["))

    async def _chat_via_responses(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> ChatResponse:
        request_params = await self._build_responses_request(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            **kwargs,
        )
        effective_model = str(request_params.get("model") or model)
        self._log_upstream_request(
            endpoint_path="responses",
            model=effective_model,
            stream=False,
        )
        logger.info(
            "Responses chat request: model={} messages={}",
            effective_model,
            len(messages),
        )
        response = await self.client.responses.create(**request_params)
        return self._convert_responses_chat_response(response, model)

    async def _stream_chat_via_responses(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> AsyncIterator[ChatChunk]:
        request_params = await self._build_responses_request(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            stream=True,
            **kwargs,
        )
        effective_model = str(request_params.get("model") or model)
        self._log_upstream_request(
            endpoint_path="responses",
            model=effective_model,
            stream=True,
        )
        logger.info("Responses stream request: model={}", effective_model)
        stream = await self.client.responses.create(**request_params)
        emitted_text = False
        emitted_reasoning = False
        response_id: str | None = None
        collected_text = ""

        try:
            async for event in stream:
                event_type = getattr(event, "type", "")

                if event_type == "response.created":
                    response_obj = getattr(event, "response", None)
                    response_id = getattr(response_obj, "id", None) or response_id
                    continue

                if event_type == "response.output_text.delta":
                    delta = getattr(event, "delta", "") or ""
                    if delta:
                        collected_text += delta
                        emitted_text = True
                        yield ChatChunk(delta=delta)
                    continue

                # Some proxies emit output_text.done without response.completed; treat as stream end (SSE-aligned) / 部分兼容网关仅发 output_text.done 不发 response.completed，与原生 SSE 行为对齐并在此结束流
                if event_type == "response.output_text.done":
                    text = getattr(event, "text", None) or ""
                    if text and not emitted_text:
                        yield ChatChunk(delta=text)
                        collected_text += text
                        emitted_text = True
                    usage = getattr(event, "usage", None)
                    usage_mode = "actual"
                    input_tokens, output_tokens, total_tokens = (
                        self._extract_usage_tokens(usage)
                    )
                    if (
                        input_tokens is None
                        and output_tokens is None
                        and total_tokens is None
                    ):
                        (
                            input_tokens,
                            output_tokens,
                            total_tokens,
                        ) = await self._retrieve_responses_usage(
                            response_id,
                        )
                    if (
                        input_tokens is None
                        and output_tokens is None
                        and total_tokens is None
                    ):
                        usage_mode = "estimated"
                        input_tokens, output_tokens, total_tokens = (
                            self._estimate_responses_stream_usage(
                                messages,
                                collected_text or text,
                            )
                        )
                    yield ChatChunk(
                        delta="",
                        finish_reason="stop",
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        metadata={"usage_mode": usage_mode},
                    )
                    logger.info(
                        "Responses stream response.output_text.done, closing upstream: model={} wire_api=responses",
                        model,
                    )
                    return

                if event_type in {
                    "response.reasoning_text.delta",
                    "response.reasoning_summary_text.delta",
                }:
                    delta = getattr(event, "delta", "") or ""
                    if delta:
                        emitted_reasoning = True
                        yield ChatChunk(delta="", reasoning_delta=delta)
                    continue

                if event_type in {
                    "response.reasoning.delta",
                    "response.thinking.delta",
                }:
                    delta = (
                        getattr(event, "delta", "") or getattr(event, "text", "") or ""
                    )
                    if delta:
                        emitted_reasoning = True
                        yield ChatChunk(delta="", reasoning_delta=delta)
                    continue

                if event_type == "response.output_item.added":
                    item = getattr(event, "item", None)
                    if getattr(item, "type", None) == "function_call":
                        yield ChatChunk(
                            delta="",
                            tool_calls=[
                                {
                                    "index": getattr(event, "output_index", None),
                                    "id": getattr(item, "call_id", None)
                                    or getattr(item, "id", None)
                                    or "",
                                    "function": {
                                        "name": getattr(item, "name", None) or "",
                                        "arguments": getattr(item, "arguments", None)
                                        or "",
                                    },
                                }
                            ],
                        )
                    continue

                if event_type == "response.function_call_arguments.delta":
                    yield ChatChunk(
                        delta="",
                        tool_calls=[
                            {
                                "index": getattr(event, "output_index", None),
                                "id": getattr(event, "item_id", None) or "",
                                "function": {
                                    "arguments": getattr(event, "delta", "") or ""
                                },
                            }
                        ],
                    )
                    continue

                if event_type == "response.function_call_arguments.done":
                    yield ChatChunk(
                        delta="",
                        tool_calls=[
                            {
                                "index": getattr(event, "output_index", None),
                                "id": getattr(event, "item_id", None) or "",
                                "function": {
                                    "name": getattr(event, "name", None) or "",
                                    "arguments": getattr(event, "arguments", None)
                                    or "{}",
                                },
                            }
                        ],
                    )
                    continue

                if event_type == "response.completed":
                    response = getattr(event, "response", None)
                    response_id = getattr(response, "id", None) or response_id
                    if response is not None and not emitted_reasoning:
                        final_reasoning = self._extract_responses_reasoning_text(
                            response,
                        )
                        if final_reasoning:
                            yield ChatChunk(
                                delta="",
                                reasoning_delta=final_reasoning,
                            )
                        else:
                            response_output = (
                                response.get("output", [])
                                if isinstance(response, dict)
                                else getattr(response, "output", [])
                            )
                            output_types = [
                                (
                                    item.get("type", "unknown")
                                    if isinstance(item, dict)
                                    else getattr(item, "type", "unknown")
                                )
                                for item in (response_output or [])
                            ]
                            reasoning_content = (
                                response.get("reasoning_content")
                                if isinstance(response, dict)
                                else getattr(response, "reasoning_content", None)
                            )
                            logger.debug(
                                "Responses stream completed without reasoning: output_types={} has_reasoning_content={}",
                                output_types,
                                bool(reasoning_content),
                            )
                    if response is not None and not emitted_text:
                        final_text = self._extract_responses_text(response)
                        if final_text:
                            collected_text += final_text
                            yield ChatChunk(delta=final_text)
                    usage = (
                        getattr(response, "usage", None)
                        if response is not None
                        else None
                    )
                    usage_mode = "actual"
                    input_tokens, output_tokens, total_tokens = (
                        self._extract_usage_tokens(usage)
                    )
                    if (
                        input_tokens is None
                        and output_tokens is None
                        and total_tokens is None
                    ):
                        (
                            input_tokens,
                            output_tokens,
                            total_tokens,
                        ) = await self._retrieve_responses_usage(
                            response_id,
                        )
                    if (
                        input_tokens is None
                        and output_tokens is None
                        and total_tokens is None
                    ):
                        usage_mode = "estimated"
                        final_text = (
                            self._extract_responses_text(response)
                            if response is not None
                            else collected_text
                        )
                        input_tokens, output_tokens, total_tokens = (
                            self._estimate_responses_stream_usage(
                                messages,
                                final_text or collected_text,
                            )
                        )
                    yield ChatChunk(
                        delta="",
                        finish_reason="stop",
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        metadata={"usage_mode": usage_mode},
                    )
                    logger.info(
                        "Responses stream response.completed, closing upstream: model={} wire_api=responses",
                        model,
                    )
                    return

                if event_type in {"response.error", "response.failed"}:
                    error_obj = getattr(event, "error", None)
                    if error_obj is not None:
                        raise RuntimeError(str(error_obj))
                    raise RuntimeError(event_type)
        finally:
            await _aclose_openai_stream(stream)

    async def _build_responses_request(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        stream: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        supports_vision = kwargs.pop("supports_vision", True)
        supports_audio = kwargs.pop("supports_audio", False)
        supports_video = kwargs.pop("supports_video", False)
        explicit_reasoning = kwargs.pop("reasoning", None)
        effective_request = kwargs.pop("_effective_model_request", None)
        model_config = kwargs.pop("model_config", None)
        if effective_request is None:
            effective_request = self.resolve_effective_model_request(
                model=model,
                model_config=(
                    model_config
                    if model_config is not None
                    else self.config.get("model_config")
                ),
                wire_api="responses",
            )
        if explicit_reasoning is None and "reasoning" in effective_request.get(
            "effective_params", {}
        ):
            explicit_reasoning = effective_request["effective_params"]["reasoning"]
        request_params: dict[str, Any] = {
            "model": effective_request["upstream_model"],
            "input": await self._convert_messages_to_responses_input(
                messages,
                supports_vision=supports_vision,
                supports_audio=supports_audio,
                supports_video=supports_video,
            ),
            "temperature": temperature,
            "top_p": top_p,
        }
        if max_tokens is not None:
            request_params["max_output_tokens"] = max_tokens
        if stream:
            request_params["stream"] = True
        if tools:
            request_params["tools"] = self._convert_tools_for_responses(tools)
        if tool_choice:
            request_params["tool_choice"] = tool_choice
        reasoning = self._build_responses_reasoning_config(
            model=model,
            explicit_reasoning=explicit_reasoning,
        )
        if reasoning is not None:
            request_params["reasoning"] = reasoning
        request_params.update(kwargs)
        return request_params

    def _build_responses_reasoning_config(
        self,
        *,
        model: str,
        explicit_reasoning: Any = None,
    ) -> Any:
        """
        Request a concise reasoning summary when the upstream model supports it.
        / 对支持的推理模型请求简洁 reasoning summary，便于前端展示“思考内容”。

        Keep caller-provided config intact and only auto-fill missing summary.
        / 保留调用方显式配置，仅在缺少 summary 时自动补齐。
        """
        if isinstance(explicit_reasoning, dict):
            if explicit_reasoning.get("summary") is not None:
                return explicit_reasoning
            if not self._supports_responses_reasoning_summary(model):
                return explicit_reasoning
            return {
                **explicit_reasoning,
                "summary": "auto",
            }

        if explicit_reasoning is not None:
            return explicit_reasoning

        if not self._supports_responses_reasoning_summary(model):
            return None

        return {"summary": "auto"}

    def _supports_responses_reasoning_summary(self, model: str) -> bool:
        normalized = str(model or "").strip().lower()
        return any(
            normalized.startswith(prefix)
            for prefix in _RESPONSES_REASONING_SUMMARY_MODEL_PREFIXES
        )

    def _convert_tools_for_responses(self, tools: list[dict]) -> list[dict]:
        converted: list[dict] = []
        has_web_search_function = False
        for tool in tools:
            if tool.get("type") == "function" and isinstance(
                tool.get("function"), dict
            ):
                function = tool["function"]
                func_name = function.get("name", "")
                # When using Responses API with native web_search support,
                # replace function-calling web_search with native web_search tool.
                # 使用 Responses API 且支持原生搜索时，用原生 web_search 替换 function calling 版本。
                if func_name == "web_search":
                    has_web_search_function = True
                    continue  # Skip — will be replaced by native web_search below
                # Omit strict: many OpenAI-compatible gateways reject or mishandle it / 省略 strict：多数兼容网关不支持或行为不一致
                converted.append(
                    {
                        "type": "function",
                        "name": func_name,
                        "description": function.get("description"),
                        "parameters": function.get("parameters"),
                    }
                )
                continue
            converted.append(tool)
        # Inject native Responses API web_search tool when the function tool was present
        # 当存在 function calling 的 web_search 时，替换为 Responses API 原生 web_search
        if has_web_search_function:
            converted.insert(0, {"type": "web_search", "search_context_size": "medium"})
        return converted

    def _responses_tool_history_mode(self) -> str:
        """
        Responses tool-history compatibility mode.
        / Responses 工具历史兼容模式。

        Some OpenAI-compatible gateways cannot reliably process structured
        function_call/function_call_output history on follow-up turns, even
        though plain text and first-round tool calls work.
        某些 OpenAI 兼容网关在后续轮次中无法稳定处理结构化
        function_call/function_call_output 历史，尽管纯文本与首轮工具调用正常。
        """
        value = (
            str((self.provider_config or {}).get("responses_tool_history_mode") or "")
            .strip()
            .lower()
        )
        if value in {"text", "structured"}:
            return value
        return "structured"

    async def _convert_messages_to_responses_input(
        self,
        messages: list[ChatMessage],
        *,
        supports_vision: bool = True,
        supports_audio: bool = False,
        supports_video: bool = False,
    ) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        textual_tool_history = self._responses_tool_history_mode() == "text"
        tool_names_by_call_id: dict[str, str] = {}

        for msg in messages:
            if msg.role == "tool":
                if textual_tool_history:
                    tool_name = tool_names_by_call_id.get(msg.tool_call_id or "", "")
                    prefix = (
                        f"Context returned by previously executed tool {tool_name}:"
                        if tool_name
                        else "Context returned by a previously executed tool:"
                    )
                    tool_output = (msg.content or "").strip()
                    converted.append(
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": (
                                f"{prefix}\n{tool_output}" if tool_output else prefix
                            ),
                        }
                    )
                    continue
                converted.append(
                    {
                        "type": "function_call_output",
                        "call_id": msg.tool_call_id or "",
                        "output": msg.content or "",
                    }
                )
                continue

            if msg.role == "assistant" and msg.tool_calls:
                if textual_tool_history:
                    assistant_text = (msg.content or "").strip()
                    for tool_call in msg.tool_calls:
                        function = tool_call.get("function") or {}
                        tc_id = tool_call.get("call_id") or tool_call.get("id") or ""
                        tool_name = function.get("name", "")
                        tool_names_by_call_id[tc_id] = tool_name
                    if assistant_text:
                        converted.append(
                            {
                                "type": "message",
                                "role": "assistant",
                                "content": assistant_text,
                            }
                        )
                    continue
                for tool_call in msg.tool_calls:
                    function = tool_call.get("function") or {}
                    tc_id = tool_call.get("call_id") or tool_call.get("id") or ""
                    tool_names_by_call_id[tc_id] = function.get("name", "")
                    converted.append(
                        {
                            "type": "function_call",
                            "call_id": tc_id,
                            "id": tool_call.get("id") or tc_id,
                            "name": function.get("name", ""),
                            "arguments": function.get("arguments", "{}") or "{}",
                            "status": "completed",
                        }
                    )
                if not (msg.content or "").strip():
                    continue

            content = await self._build_responses_message_content(
                msg,
                supports_vision=supports_vision,
                supports_audio=supports_audio,
                supports_video=supports_video,
            )
            converted.append(
                {
                    "type": "message",
                    "role": msg.role,
                    "content": content,
                }
            )

        return converted

    async def _build_responses_message_content(
        self,
        msg: ChatMessage,
        *,
        supports_vision: bool = True,
        supports_audio: bool = False,
        supports_video: bool = False,
    ) -> str | list[dict[str, Any]]:
        if msg.role != "user" or not msg.attachments:
            return msg.content or ""

        parts: list[dict[str, Any]] = []
        if msg.content:
            parts.append({"type": "input_text", "text": msg.content})

        for att in msg.attachments:
            att_type = str(att.get("type") or "").lower()
            url = str(att.get("url") or "").strip()
            name = att.get("name") or att.get("filename") or "file"
            att_mime = str(att.get("mime_type") or "")
            attachment_id = att.get("attachment_id")

            if att_type == "image":
                if supports_vision and url:
                    resolved = await self._resolve_image_url_for_llm(
                        url,
                        att_mime,
                        attachment_id=attachment_id,
                    )
                    if resolved:
                        parts.append(
                            {
                                "type": "input_image",
                                "image_url": resolved,
                                "detail": "auto",
                            }
                        )
                    else:
                        hint = (
                            f"[Image: {name or 'uploaded image'} "
                            "(could not load for model)]"
                        )
                        parts.append({"type": "input_text", "text": hint})
                else:
                    parts.append({"type": "input_text", "text": f"[Image: {name}]"})
                continue

            if att_type == "file":
                if url:
                    parts.append(
                        {
                            "type": "input_file",
                            "file_url": url,
                            "filename": str(name),
                        }
                    )
                else:
                    parts.append({"type": "input_text", "text": f"[File: {name}]"})
                continue

            if att_type == "audio":
                if supports_audio and url:
                    parts.append(
                        {
                            "type": "input_file",
                            "file_url": url,
                            "filename": str(name),
                        }
                    )
                else:
                    parts.append({"type": "input_text", "text": f"[Audio: {name}]"})
                continue

            if att_type == "video":
                if supports_video and url:
                    parts.append(
                        {
                            "type": "input_file",
                            "file_url": url,
                            "filename": str(name),
                        }
                    )
                else:
                    parts.append({"type": "input_text", "text": f"[Video: {name}]"})
                continue

            parts.append({"type": "input_text", "text": f"[Attachment: {name}]"})

        return parts or (msg.content or "")

    def _extract_responses_text(self, response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text:
            return output_text

        parts: list[str] = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) != "message":
                continue
            for content in getattr(item, "content", []) or []:
                if getattr(content, "type", None) == "output_text":
                    text = getattr(content, "text", None)
                    if text:
                        parts.append(text)
        return "".join(parts)

    def _extract_responses_tool_calls(self, response: Any) -> list[dict] | None:
        tool_calls: list[dict] = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) != "function_call":
                continue
            call_id = getattr(item, "call_id", None) or getattr(item, "id", None) or ""
            tool_calls.append(
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": getattr(item, "name", None) or "",
                        "arguments": getattr(item, "arguments", None) or "{}",
                    },
                }
            )
        return tool_calls or None

    def _extract_responses_reasoning_text(self, response: Any) -> str | None:
        parts: list[str] = []

        def _field(value: Any, name: str) -> Any:
            if isinstance(value, dict):
                return value.get(name)
            return getattr(value, name, None)

        def _append_text(value: Any) -> None:
            if not isinstance(value, str):
                return
            text = value.strip()
            if text and text not in parts:
                parts.append(text)

        def _append_candidates(value: Any, *field_names: str) -> None:
            if value is None:
                return
            if isinstance(value, list):
                for item in value:
                    _append_candidates(item, *field_names)
                return

            if isinstance(value, str):
                _append_text(value)
                return

            for field_name in field_names:
                _append_text(_field(value, field_name))

        for item in _field(response, "output") or []:
            if _field(item, "type") != "reasoning":
                continue

            item_content = _field(item, "content")
            if isinstance(item_content, str):
                _append_text(item_content)
                continue

            if isinstance(item_content, list):
                _append_candidates(
                    item_content,
                    "text",
                    "thinking",
                    "summary_text",
                    "reasoning_content",
                )

            for summary_item in _field(item, "summary") or []:
                _append_candidates(summary_item, "text", "summary_text")

        if not parts:
            _append_candidates(
                _field(response, "reasoning_content"),
                "text",
                "summary_text",
                "thinking",
            )

        if not parts:
            _append_candidates(
                _field(response, "reasoning"),
                "text",
                "summary_text",
                "thinking",
            )

        if not parts:
            for item in _field(response, "output") or []:
                if _field(item, "type") != "message":
                    continue
                for content_item in _field(item, "content") or []:
                    if _field(content_item, "type") not in {"thinking", "reasoning"}:
                        continue
                    _append_candidates(
                        content_item,
                        "thinking",
                        "text",
                        "reasoning_content",
                    )

        if not parts:
            return None
        return "\n\n".join(parts)

    def _convert_responses_chat_response(
        self, response: Any, model: str
    ) -> ChatResponse:
        tool_calls = self._extract_responses_tool_calls(response)
        reasoning_content = self._extract_responses_reasoning_text(response)
        usage = getattr(response, "usage", None)
        input_tokens, output_tokens, total_tokens = self._extract_usage_tokens(usage)
        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content=self._extract_responses_text(response),
                reasoning_content=reasoning_content,
                tool_calls=tool_calls,
            ),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            model=model,
            finish_reason="stop"
            if getattr(response, "status", None) == "completed"
            else getattr(response, "status", None),
            tool_calls=tool_calls,
            metadata={"protocol_path": "responses"},
            raw_response=response.model_dump()
            if hasattr(response, "model_dump")
            else None,
        )

    async def _fetch_audio_bytes(self, url: str) -> bytes | None:
        """
        Resolve audio URL to bytes for input_audio. Supports data URL or HTTP GET.
        / 将音频 URL 解析为字节供 input_audio 使用。支持 data URL 或 HTTP GET。

        Returns:
            Audio bytes, or None on failure / 成功返回音频字节，失败返回 None
        """
        if not url or not url.strip():
            return None
        url = url.strip()
        # data URL (data:audio/...;base64,...) / data URL 音频（base64）
        if url.startswith("data:audio"):
            payload = extract_data_url_payload(url, media_prefix="audio")
            if payload is not None:
                try:
                    return base64.b64decode(payload)
                except Exception as e:
                    logger.warning("Audio data URL base64 decode failed: {}", e)
                    return None
            return None
        try:
            await UrlValidator.validate(url)
        except SSRFBlockedError as e:
            logger.warning("Audio fetch URL blocked (SSRF): {}", e)
            return None
        try:
            async with httpx.AsyncClient(timeout=_AUDIO_FETCH_TIMEOUT_SEC) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                content_length = resp.headers.get("content-length")
                try:
                    cl = (
                        int(content_length)
                        if (content_length and content_length.strip().isdigit())
                        else None
                    )
                except (ValueError, AttributeError):
                    cl = None
                if cl is not None and cl > _AUDIO_MAX_BYTES:
                    logger.warning(
                        "Audio too large (content-length={} > {}), skip native",
                        cl,
                        _AUDIO_MAX_BYTES,
                    )
                    return None
                data = resp.content
                if len(data) > _AUDIO_MAX_BYTES:
                    logger.warning(
                        "Audio body too large ({} > {}), skip native",
                        len(data),
                        _AUDIO_MAX_BYTES,
                    )
                    return None
                return data
        except Exception as e:
            logger.warning("Fetch audio URL failed: {}", e)
            return None

    async def _resolve_image_url_for_llm(
        self,
        att_url: str,
        att_mime: str,
        *,
        attachment_id: object = None,
    ) -> str | None:
        """
        Convert attachment / remote image URL to data URL for vendor multimodal APIs.
        """
        db = self.config.get("internal_db")
        tenant_id = self.config.get("internal_tenant_id")
        return await resolve_image_url_for_llm(
            att_url,
            att_mime or None,
            db=db,
            tenant_id=tenant_id,
            attachment_id=attachment_id,
        )

    async def _convert_messages(
        self,
        messages: list[ChatMessage],
        *,
        supports_vision: bool = True,
        supports_audio: bool = False,
        supports_video: bool = False,
    ) -> list[dict]:
        """
        Convert message format / 转换消息格式

        Args:
            messages: Unified format message list / 统一格式的消息列表
            supports_vision: Whether the target model supports vision (image_url content).
                             When False, image attachments are converted to text hints.
                             目标模型是否支持视觉（image_url 内容）。为 False 时图片附件转为文字提示。
            supports_audio: Whether the target model supports audio input. When False, audio → text hint.
                            目标模型是否支持音频输入。为 False 时音频附件转为文字提示。
            supports_video: Whether the target model supports video input. When False, video → text hint.
                            目标模型是否支持视频输入。为 False 时视频附件转为文字提示。

        Returns:
            OpenAI format message list / OpenAI 格式的消息列表
        """
        openai_messages = []

        for msg in messages:
            openai_msg: dict = {
                "role": msg.role,
            }

            # Multimodal: user message with attachments -> content[] / 多模态：user 含附件时转为 content 数组
            if msg.role == "user" and msg.attachments:
                content_parts: list[dict] = []
                if msg.content:
                    content_parts.append({"type": "text", "text": msg.content})
                for att in msg.attachments:
                    att_type = att.get("type", "")
                    att_url = att.get("url", "")
                    att_name = att.get("name", "")
                    att_mime = att.get("mime_type", "")
                    attachment_id = att.get("attachment_id")
                    if att_type == "image" and att_url:
                        if supports_vision:
                            resolved = await self._resolve_image_url_for_llm(
                                att_url,
                                att_mime,
                                attachment_id=attachment_id,
                            )
                            if resolved:
                                content_parts.append(
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": resolved},
                                    }
                                )
                            else:
                                hint = (
                                    f"[Image: {att_name or 'uploaded image'} "
                                    "(could not load for model)]"
                                )
                                content_parts.append({"type": "text", "text": hint})
                        else:
                            # Non-vision model: degrade to text hint / 非视觉模型：降级为文字提示
                            hint = f"[Image: {att_name or 'uploaded image'}]"
                            content_parts.append({"type": "text", "text": hint})
                    elif att_type == "audio":
                        # Audio: input_audio if native supported, else text hint / 音频：原生支持用 input_audio，否则文字提示
                        hint = f"[Audio: {att_name or 'uploaded audio'}]"
                        if not att_url:
                            content_parts.append({"type": "text", "text": hint})
                        elif supports_audio and SUPPORTS_NATIVE_AUDIO:
                            bytes_result = await self._fetch_audio_bytes(att_url)
                            if bytes_result is None:
                                content_parts.append({"type": "text", "text": hint})
                            else:
                                fmt = (
                                    _AUDIO_MIME_TO_OPENAI_FORMAT.get(att_mime) or "mpeg"
                                )
                                b64_str = base64.b64encode(bytes_result).decode("ascii")
                                content_parts.append(
                                    {
                                        "type": "input_audio",
                                        "input_audio": {"data": b64_str, "format": fmt},
                                    }
                                )
                        else:
                            content_parts.append({"type": "text", "text": hint})
                    elif att_type == "video" and att_url:
                        # Video: vendor-native TBD; use text hint for now / 视频：待厂商 API 扩展原生格式，暂用文字提示
                        if supports_video:
                            hint = f"[Video: {att_name or 'uploaded video'}]"
                            content_parts.append({"type": "text", "text": hint})
                        else:
                            hint = f"[Video: {att_name or 'uploaded video'}]"
                            content_parts.append({"type": "text", "text": hint})
                    elif att_type == "file" and att_name:
                        file_hint = f"[Attached file: {att_name}"
                        if att_mime:
                            file_hint += f", type: {att_mime}"
                        file_hint += "]"
                        content_parts.append({"type": "text", "text": file_hint})
                openai_msg["content"] = content_parts if content_parts else msg.content
            else:
                openai_msg["content"] = msg.content

            if msg.name:
                openai_msg["name"] = msg.name

            if msg.tool_calls:
                openai_msg["tool_calls"] = msg.tool_calls

            if msg.tool_call_id:
                openai_msg["tool_call_id"] = msg.tool_call_id

            openai_messages.append(openai_msg)

        return openai_messages

    def _convert_chat_response(
        self, response: ChatCompletion, model: str
    ) -> ChatResponse:
        """
        Convert OpenAI chat response to unified format / 转换 OpenAI 聊天响应为统一格式
        """
        if not response.choices:
            return ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                model=model,
                finish_reason="stop",
                metadata={"protocol_path": "chat_completions"},
            )
        choice = response.choices[0]
        message = choice.message

        # Convert OpenAI SDK tool_calls objects to dict list / 将 OpenAI SDK tool_calls 对象转为 dict 列表
        tool_calls_dicts: list[dict] | None = None
        if message.tool_calls:
            tool_calls_dicts = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]

        # Build unified message format / 构建统一消息格式
        chat_message = ChatMessage(
            role=message.role,
            content=message.content or "",
            tool_calls=tool_calls_dicts,
        )

        # Extract token usage / 提取 Token 使用量
        usage = response.usage
        input_tokens, output_tokens, total_tokens = self._extract_usage_tokens(usage)

        return ChatResponse(
            message=chat_message,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            model=model,
            finish_reason=choice.finish_reason,
            tool_calls=tool_calls_dicts,
            metadata={"protocol_path": "chat_completions"},
            raw_response=response.model_dump()
            if hasattr(response, "model_dump")
            else None,
        )

    def _convert_chat_chunk(self, chunk: ChatCompletionChunk, model: str) -> ChatChunk:
        """
        Convert OpenAI streaming response chunk to unified format / 转换 OpenAI 流式响应块为统一格式
        """
        _ = model
        if not chunk.choices:
            return ChatChunk(delta="")
        choice = chunk.choices[0]
        delta = choice.delta

        # Keep reasoning delta separate from final answer for "thinking" UI / 将 reasoning 与最终答复分离，便于前端展示思考过程
        delta_content = delta.content or ""
        reasoning_delta = getattr(delta, "reasoning_content", None) or ""

        # Extract token usage (included in the last chunk) / 提取 Token 使用量（最后一个块包含）
        usage = chunk.usage
        input_tokens, output_tokens, total_tokens = self._extract_usage_tokens(usage)

        # Convert OpenAI SDK tool_calls to serializable dict list (with index for incremental merging) / 将 OpenAI SDK tool_calls 对象转为可序列化 dict 列表
        tool_calls_dicts: list[dict] | None = None
        if delta.tool_calls:
            tool_calls_dicts = []
            for tc in delta.tool_calls:
                func = getattr(tc, "function", None)
                tool_calls_dicts.append(
                    {
                        "index": getattr(tc, "index", None),
                        "id": getattr(tc, "id", None) or "",
                        "type": getattr(tc, "type", None) or "function",
                        "function": {
                            "name": getattr(func, "name", None) or "",
                            "arguments": getattr(func, "arguments", None) or "",
                        },
                    }
                )

        return ChatChunk(
            delta=delta_content,
            reasoning_delta=reasoning_delta,
            role=delta.role,
            finish_reason=choice.finish_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            tool_calls=tool_calls_dicts,
        )

    async def generate_image(
        self,
        prompt: str,
        model: str,
        size: str = "1024x1024",
        quality: str = "standard",
        style: str = "vivid",
        n: int = 1,
        **kwargs,
    ) -> ImageGenerationResponse:
        """
        Image generation (calls OpenAI /v1/images/generations) / 图像生成
        """
        try:
            logger.info(
                "Image generation request: model={} size={} quality={} n={}",
                model,
                size,
                quality,
                n,
            )

            request_params: dict = {
                "model": model,
                "prompt": prompt,
                "size": size,
                "quality": quality,
                "n": n,
                "response_format": "url",
            }
            # style only supported by dall-e-3 / style 仅 dall-e-3 支持
            if "dall-e-3" in model:
                request_params["style"] = style

            request_params.update(kwargs)

            response = await self.client.images.generate(**request_params)

            images: list[ImageResponse] = []
            revised_prompt: str | None = None
            for item in response.data:
                url = item.url or ""
                b64 = item.b64_json or ""
                is_base64 = bool(b64 and not url)
                rp = getattr(item, "revised_prompt", None)
                if rp and not revised_prompt:
                    revised_prompt = rp
                images.append(
                    ImageResponse(
                        url=b64 if is_base64 else url,
                        is_base64=is_base64,
                        revised_prompt=rp,
                    )
                )

            return ImageGenerationResponse(
                images=images,
                model=model,
                revised_prompt=revised_prompt,
            )

        except AIGatewayError:
            raise
        except Exception as e:
            logger.error("Image generation error: model={} error={}", model, str(e))
            raise convert_openai_error(
                e, provider_code="openai", model_code=model
            ) from e

    def get_supported_features(self) -> dict[str, bool]:
        """
        Get supported features / 获取支持的功能
        """
        return {
            "chat": True,
            "streaming": True,
            "function_calling": True,
            "vision": True,
            "embedding": True,
            "image_generation": True,
        }


__all__ = [
    "OpenAIAdapter",
]
