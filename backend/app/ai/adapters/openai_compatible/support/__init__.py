"""Support helpers for OpenAI-compatible adapter internals."""

from app.ai.adapters.openai_compatible.support.gateway_entrypoints import (
    OpenAIAdapterGatewayEntrypointsMixin,
)
from app.ai.adapters.openai_compatible.support.model_request_runtime import (
    RESPONSES_REASONING_SUMMARY_MODEL_PREFIXES,
    OpenAIAdapterModelRequestMixin,
)
from app.ai.adapters.openai_compatible.support.multimodal_support import (
    SUPPORTS_NATIVE_AUDIO,
    OpenAIAdapterMultimodalMixin,
)
from app.ai.adapters.openai_compatible.support.native_web_search_support import (
    OpenAIAdapterNativeWebSearchMixin,
)
from app.ai.adapters.openai_compatible.support.non_chat_runtime import (
    OpenAIAdapterNonChatRuntimeMixin,
)
from app.ai.adapters.openai_compatible.support.protocol_entrypoints import (
    OpenAIAdapterProtocolEntrypointsMixin,
)
from app.ai.adapters.openai_compatible.support.stream_cleanup import (
    aclose_openai_stream,
)
from app.ai.adapters.openai_compatible.support.upstream_runtime import (
    OpenAIAdapterUpstreamRuntimeMixin,
)
from app.ai.adapters.openai_compatible.support.usage_runtime import (
    OpenAIAdapterUsageRuntimeMixin,
)

__all__ = [
    "OpenAIAdapterGatewayEntrypointsMixin",
    "OpenAIAdapterModelRequestMixin",
    "OpenAIAdapterMultimodalMixin",
    "OpenAIAdapterNativeWebSearchMixin",
    "OpenAIAdapterNonChatRuntimeMixin",
    "OpenAIAdapterProtocolEntrypointsMixin",
    "OpenAIAdapterUpstreamRuntimeMixin",
    "OpenAIAdapterUsageRuntimeMixin",
    "RESPONSES_REASONING_SUMMARY_MODEL_PREFIXES",
    "SUPPORTS_NATIVE_AUDIO",
    "aclose_openai_stream",
]
