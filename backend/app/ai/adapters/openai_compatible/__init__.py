"""OpenAI compatible adapter support modules."""

from app.ai.adapters.openai_compatible.capabilities import (
    OpenAIProtocolCapabilities,
    normalize_wire_api,
)
from app.ai.adapters.openai_compatible.client_factory import (
    build_chat_completions_v1_retry_base_url,
    build_openai_client,
    resolve_retry_client,
)
from app.ai.adapters.openai_compatible.compat.legacy_protocol_execution import (
    execute_legacy_chat,
    execute_legacy_stream,
    responses_tool_call_fallback_enabled,
    stream_chat_completions_with_sync_rescue,
)
from app.ai.adapters.openai_compatible.compat.legacy_protocol_policy import (
    extract_status_code,
    should_fallback_from_responses_error,
    should_skip_sync_rescue_after_stream_error,
)
from app.ai.adapters.openai_compatible.request_builder import (
    build_endpoint_url,
    resolve_chat_endpoint_path,
)
from app.ai.adapters.openai_compatible.response_mapper import (
    attach_protocol_metadata,
)
from app.ai.adapters.openai_compatible.timeout_policy import (
    DEFAULT_STREAM_TIMEOUT_SECONDS,
    normalize_timeout_seconds,
)

__all__ = [
    "DEFAULT_STREAM_TIMEOUT_SECONDS",
    "OpenAIProtocolCapabilities",
    "attach_protocol_metadata",
    "build_chat_completions_v1_retry_base_url",
    "build_endpoint_url",
    "build_openai_client",
    "execute_legacy_chat",
    "execute_legacy_stream",
    "extract_status_code",
    "normalize_timeout_seconds",
    "normalize_wire_api",
    "responses_tool_call_fallback_enabled",
    "resolve_chat_endpoint_path",
    "resolve_retry_client",
    "should_fallback_from_responses_error",
    "should_skip_sync_rescue_after_stream_error",
    "stream_chat_completions_with_sync_rescue",
]
