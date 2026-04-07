"""Failure classification for orchestration diagnostics."""

from __future__ import annotations

from typing import Any

from app.ai.exceptions import (
    AIGatewayError,
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.ai.tools.types import ToolResult

from .types import ProviderFailureKind


class FailureClassifier:
    @staticmethod
    def _should_ignore_tool_failure(
        result: ToolResult,
        *,
        successful_fetch_url: bool,
    ) -> bool:
        error_type = str(result.error_type or "").strip()
        if error_type == "search_candidates_exhausted" and successful_fetch_url:
            return True
        return False

    @staticmethod
    def classify_exception(
        exc: BaseException,
    ) -> tuple[ProviderFailureKind, dict[str, Any]]:
        if isinstance(exc, ProviderTimeoutError):
            return "provider_timeout", {"kind": "provider_timeout", "error": str(exc)}
        if isinstance(exc, ProviderRateLimitError):
            return "provider_rate_limit", {
                "kind": "provider_rate_limit",
                "error": str(exc),
            }
        if isinstance(exc, ProviderConnectionError):
            return "provider_unavailable", {
                "kind": "provider_unavailable",
                "error": str(exc),
            }
        if isinstance(exc, AIGatewayError):
            status_code = int(getattr(exc, "status_code", 0) or 0)
            if 500 <= status_code < 600:
                return "provider_http_5xx", {
                    "kind": "provider_http_5xx",
                    "error": str(exc),
                    "status_code": status_code,
                }
            return "provider_bad_response", {
                "kind": "provider_bad_response",
                "error": str(exc),
                "status_code": status_code,
            }
        if exc.__class__.__name__ in {"CancelledError", "GeneratorExit"}:
            return "server_interrupt", {"kind": "server_interrupt", "error": str(exc)}
        return "none", {}

    @staticmethod
    def classify_tool_results(
        tool_results: list[ToolResult],
    ) -> tuple[ProviderFailureKind, list[dict[str, Any]]]:
        events: list[dict[str, Any]] = []
        kind: ProviderFailureKind = "none"
        successful_fetch_url = any(
            result.success and str(result.name or "").strip() == "fetch_url"
            for result in tool_results
        )
        for result in tool_results:
            if result.success:
                continue
            if FailureClassifier._should_ignore_tool_failure(
                result,
                successful_fetch_url=successful_fetch_url,
            ):
                continue
            events.append(
                {
                    "tool_name": result.name,
                    "error_type": result.error_type or "tool_execution_error",
                    "error": result.error,
                }
            )
            if result.error_type == "timeout":
                kind = "tool_timeout"
            elif kind == "none":
                kind = "tool_execution_error"
        return kind, events


__all__ = ["FailureClassifier"]
