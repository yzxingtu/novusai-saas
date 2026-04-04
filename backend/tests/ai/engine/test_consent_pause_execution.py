import asyncio
from types import SimpleNamespace

from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.recovery_manager import RecoveryManager
from app.ai.engine.stream_handler import StreamExecutionHandler
from app.ai.engine.types import (
    ExecutionRequest,
    IntentPlan,
    PreparedExecution,
    RecoveryDecision,
)
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


def _make_agent() -> SimpleNamespace:
    provider = SimpleNamespace(
        code="test-provider",
        type="mock",
        base_url="",
        config={},
        decrypt_key=lambda: "fake-key",
    )
    model = SimpleNamespace(
        provider=provider,
        code="test-model",
        supports_vision=False,
        supports_audio=False,
        supports_video=False,
        supports_streaming=True,
        config={},
    )
    return SimpleNamespace(
        id=1,
        name="Consent Agent",
        system_prompt="",
        temperature=0.0,
        max_tokens=256,
        top_p=1.0,
        model=model,
    )


def _build_prepared_execution(pending_payload: dict[str, object]) -> tuple[PreparedExecution, list[ChatMessage]]:
    messages = [
        ChatMessage(role="user", content="Please delete this item."),
        ChatMessage(
            role="assistant",
            content="Need your confirmation before proceeding.",
            metadata={"pending_consent": pending_payload},
        ),
    ]
    intent = IntentPlan(
        intent_id="intent-consent",
        kind="consent",
        family="general",
        order=1,
        user_visible_label="Approve delete",
        source_text="",
        status="awaiting_consent",
        requires_tools=True,
        metadata={"pending_consent": pending_payload},
    )
    prep = PreparedExecution(
        messages=list(messages),
        tools=[],
        all_tools=[],
        intent_plan=[intent],
        execution_path="normal",
    )
    prep.rag_sources = []
    prep.rag_source_kinds = []
    return prep, list(messages)


async def _drain_async_generator(generator):
    async for _ in generator:
        pass

def test_conversation_pauses_for_consent(monkeypatch):
    agent = _make_agent()
    pending_payload = {"tool_name": "delete_record", "arguments": {"id": 123}}
    prep, _ = _build_prepared_execution(pending_payload)
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        conversation_id=42,
        stream=False,
        messages=[ChatMessage(role="user", content="Delete the file.")],
        interaction_updates=[],
    )
    decision = RecoveryDecision(
        action="pause_for_consent",
        reason="pending_consent",
        metadata={"pending_consent": pending_payload},
        unfinished_intent_ids=["intent-consent"],
    )

    def _fake_decide(*_args, **_kwargs):
        return decision

    monkeypatch.setattr(RecoveryManager, "decide", _fake_decide)

    async def fake_prepare(self, agent, request, skill_result=None):
        return prep

    monkeypatch.setattr(ConversationEngine, "_prepare_execution", fake_prepare)

    async def fake_call(self, agent, messages, **kwargs):
        return ChatResponse(
            message=ChatMessage(role="assistant", content="Need your consent"),
            total_tokens=0,
            output_tokens=0,
        )

    monkeypatch.setattr(ConversationEngine, "_call_llm", fake_call)

    engine = ConversationEngine(db=None, gateway=None, sandbox=None)
    result = asyncio.run(engine.execute(agent, request))

    assert not result.partial
    assert result.interrupted
    assert not result.success
    assert result.completion_reason == "pending_consent"
    assert result.diagnostics["current_state"] == "awaiting_consent"
    assert any(
        (msg.get("metadata") or {}).get("pending_consent", {}).get("tool_name")
        == "delete_record"
        for msg in result.messages
    )
    assert result.output == "Need your consent"


def test_stream_pauses_for_consent(monkeypatch):
    agent = _make_agent()
    pending_payload = {"tool_name": "delete_record", "arguments": {"id": 456}}
    prep, _ = _build_prepared_execution(pending_payload)
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        conversation_id=99,
        stream=True,
        messages=[ChatMessage(role="user", content="Delete it now.")],
        interaction_updates=[],
    )
    decision = RecoveryDecision(
        action="pause_for_consent",
        reason="pending_consent",
        metadata={"pending_consent": pending_payload},
        unfinished_intent_ids=["intent-consent"],
    )

    def _fake_decide(*_args, **_kwargs):
        return decision

    monkeypatch.setattr(RecoveryManager, "decide", _fake_decide)

    engine = ConversationEngine(db=None, gateway=None, sandbox=None)

    async def fake_stream(*args, **kwargs):
        yield ChatChunk(
            delta="Need your consent",
            total_tokens=1,
            metadata={
                "runtime_model_info": {
                    "model_id": 1,
                    "model_name": "mock",
                    "provider_id": 2,
                    "provider_name": "mock",
                },
                "runtime_turn_record": {},
            },
        )

    monkeypatch.setattr(engine, "_stream_llm_chunks", fake_stream)

    handler = StreamExecutionHandler(
        engine=engine,
        agent=agent,
        request=request,
        prep=prep,
        start_time=0,
        on_complete=None,
    )

    captured: dict[str, object] = {}
    handler._schedule_on_complete = lambda result: captured.setdefault("result", result)

    asyncio.run(_drain_async_generator(handler.generate()))
    result = captured["result"]

    assert not result.partial
    assert result.interrupted
    assert not result.success
    assert result.completion_reason == "pending_consent"
    assert result.diagnostics["current_state"] == "awaiting_consent"
    assert any(
        (msg.get("metadata") or {}).get("pending_consent", {}).get("tool_name")
        == "delete_record"
        for msg in result.messages
    )
    assert result.output == "Need your consent"
