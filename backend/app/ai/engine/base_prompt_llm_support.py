"""
LLM gateway call bindings for BaseEngine prompt/runtime support.
"""

from __future__ import annotations

from .llm_call_helpers import (
    apply_llm_response_metadata as _apply_llm_response_metadata_impl,
)
from .llm_call_helpers import (
    prepare_llm_gateway_call as _prepare_llm_gateway_call_impl,
)


class BasePromptLLMSupportMixin:
    """Binds LLM gateway call helpers onto BaseEngine."""

    _prepare_llm_gateway_call = staticmethod(_prepare_llm_gateway_call_impl)
    _apply_llm_response_metadata = staticmethod(_apply_llm_response_metadata_impl)


__all__ = ["BasePromptLLMSupportMixin"]
