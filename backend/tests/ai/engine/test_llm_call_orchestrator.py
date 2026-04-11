from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.ai.engine.llm_call_helpers import LLMCallContext, PreparedLLMCall
from app.ai.engine.llm_call_orchestrator import execute_llm_call
from app.ai.engine.types import ToolUsePolicy
from app.ai.types import ChatMessage, ChatResponse


@pytest.mark.asyncio
async def test_execute_llm_call_invokes_prepare_gateway_and_apply_metadata() -> None:
    messages = [ChatMessage(role="user", content="hello")]
    prepared = PreparedLLMCall(
        effective_policy=ToolUsePolicy(
            family="none",
            mode="auto",
            allowed_tool_names=[],
            retry_on_contract_breach=False,
            reason="test",
        ),
        llm_call_context=LLMCallContext(
            provider_code="provider-a",
            model_code="model-a",
            routed_model_id=None,
            route_reason=None,
            supports_vision=False,
            supports_audio=False,
            supports_video=False,
        ),
        openai_tools=None,
        gateway_kwargs={"messages": ["payload"], "model": "model-a"},
    )
    prepare = AsyncMock(return_value=prepared)
    response = ChatResponse(message=ChatMessage(role="assistant", content="ok"))
    gateway = SimpleNamespace(chat=AsyncMock(return_value=response))
    apply = Mock(return_value=response)
    logger = Mock()

    result = await execute_llm_call(
        db=Mock(),
        gateway=gateway,
        logger=logger,
        runtime_tag="runtime@test",
        agent=Mock(id=123),
        messages=messages,
        tools=None,
        all_tool_names=None,
        tool_use_policy=None,
        breach_retry_result=None,
        tenant_id=1,
        user_id=2,
        conversation_id=3,
        billing_context=None,
        route_result=None,
        log_user_type=None,
        prepare_llm_gateway_call=prepare,
        apply_llm_response_metadata=apply,
    )

    assert result is response
    prepare.assert_awaited_once()
    assert prepare.await_args.kwargs["messages"] is messages
    gateway.chat.assert_awaited_once_with(**prepared.gateway_kwargs)
    apply.assert_called_once_with(
        response,
        llm_call_context=prepared.llm_call_context,
    )
    logger.info.assert_called_once()
