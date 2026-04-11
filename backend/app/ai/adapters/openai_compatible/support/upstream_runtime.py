"""Upstream client/runtime helpers for OpenAI-compatible adapter facades."""

from __future__ import annotations

import json
from typing import Any

from app.ai.adapters.openai_compatible.client_factory import (
    build_chat_completions_v1_retry_base_url,
    resolve_retry_client,
)
from app.ai.adapters.openai_compatible.request_builder import build_endpoint_url
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")


class OpenAIAdapterUpstreamRuntimeMixin:
    """Shared base-url, retry-client, and upstream logging helpers."""

    @staticmethod
    def _clean_base_url(base_url: str | None) -> str | None:
        cleaned_base_url = str(base_url or "").strip()
        return cleaned_base_url or None

    def _get_effective_base_url(self) -> str:
        return (self.base_url or "https://api.openai.com/v1").rstrip("/")

    def _build_endpoint_url(self, endpoint_path: str) -> str:
        return build_endpoint_url(base_url=self.base_url, endpoint_path=endpoint_path)

    def _build_chat_completions_v1_retry_base_url(self) -> str | None:
        return build_chat_completions_v1_retry_base_url(self.base_url)

    def _get_chat_completions_v1_retry_client(self) -> Any | None:
        retry_client, retry_base_url = resolve_retry_client(
            api_key=self.api_key,
            base_url=self.base_url,
            cached_client=self._chat_completions_v1_retry_client,
            cached_base_url=self._chat_completions_v1_retry_base_url,
        )
        self._chat_completions_v1_retry_client = retry_client
        self._chat_completions_v1_retry_base_url = retry_base_url
        return self._chat_completions_v1_retry_client

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

    @staticmethod
    def _format_preview(payload: Any, limit: int = 400) -> str:
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


__all__ = ["OpenAIAdapterUpstreamRuntimeMixin"]
