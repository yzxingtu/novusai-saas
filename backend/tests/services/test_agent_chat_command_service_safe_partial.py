"""
Test type: behavioral
Scope: non-streaming chat command handling for platform-owned safe partial output.
Mock strategy: no LLM or tool executor mocks; tests the service boundary helper
that decides whether a deterministic platform fallback may be persisted.
"""

from app.ai.engine.types import ExecutionResult
from app.services.ai.agent_chat_command_service import _promote_safe_partial_output


def test_provider_failure_without_safe_output_still_raises_upstream() -> None:
    result = ExecutionResult(
        success=False,
        output="",
        partial=True,
        completion_reason="provider_timeout",
        error="AI 供应商请求超时",
    )

    promoted = _promote_safe_partial_output(result)

    assert promoted is False
    assert result.success is False
    assert result.error == "AI 供应商请求超时"
