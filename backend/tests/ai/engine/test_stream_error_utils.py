"""Test type: behavioral.

Scope: stream error public-message sanitization.
Mocked dependencies: none; imports the helper module directly.
"""

from __future__ import annotations

import sys
import types
from importlib import import_module
from pathlib import Path

from app.ai.exceptions import (
    AIGatewayError,
    ProviderAuthError,
    ProviderConnectionError,
    ProviderError,
    ProviderTimeoutError,
)
from app.core.i18n import _
from app.middleware.trace import trace_id_var

ENGINE_DIR = Path(__file__).resolve().parents[3] / "app" / "ai" / "engine"
if "app.ai.engine" not in sys.modules:
    engine_pkg = types.ModuleType("app.ai.engine")
    engine_pkg.__path__ = [str(ENGINE_DIR)]
    sys.modules["app.ai.engine"] = engine_pkg

stream_error_utils = import_module("app.ai.engine.stream_error_utils")
is_stream_interruption_error = stream_error_utils.is_stream_interruption_error
resolve_stream_public_error_message = (
    stream_error_utils.resolve_stream_public_error_message
)
trace_payload = stream_error_utils.trace_payload


def test_trace_payload_injects_trace_id_only_when_missing() -> None:
    token = trace_id_var.set("trace-123")
    try:
        assert trace_payload({"event": "done"})["trace_id"] == "trace-123"
        assert trace_payload({"event": "done", "trace_id": "existing"})["trace_id"] == (
            "existing"
        )
    finally:
        trace_id_var.reset(token)


def test_is_stream_interruption_error_detects_disconnect_keywords() -> None:
    assert (
        is_stream_interruption_error(RuntimeError("client disconnected [trace_id=abc]"))
        is True
    )
    assert is_stream_interruption_error(RuntimeError("provider timeout")) is False


def test_resolve_stream_public_error_message_prefers_gateway_message() -> None:
    error = AIGatewayError("provider said no [trace_id=trace-1]")

    assert resolve_stream_public_error_message(error) == "provider said no"


def test_resolve_stream_public_error_message_suppresses_html_gateway_payload() -> None:
    error = ProviderError(
        "<!DOCTYPE html><html><body>Bad gateway</body></html>",
        status_code=502,
    )

    assert resolve_stream_public_error_message(error) == _(
        "ai.error.provider_server_error"
    )


def test_resolve_stream_public_error_message_localizes_generic_connection_error() -> (
    None
):
    error = ProviderConnectionError("Connection error.")

    assert resolve_stream_public_error_message(error) == _(
        "ai.error.provider_connection"
    )


def test_resolve_stream_public_error_message_localizes_generic_timeout_error() -> None:
    error = ProviderTimeoutError("Request timed out.")

    assert resolve_stream_public_error_message(error) == _("ai.error.provider_timeout")


def test_resolve_stream_public_error_message_sanitizes_provider_auth_detail() -> None:
    error = ProviderAuthError("Incorrect API key provided: sk-test-secret")

    message = resolve_stream_public_error_message(error)

    assert message == _("ai.error.provider_auth")
    assert "sk-test-secret" not in message
    assert "Incorrect API key" not in message
