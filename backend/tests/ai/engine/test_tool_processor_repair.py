"""Tests for _try_repair_json enhancements."""
import asyncio
import json

from app.ai.engine.execution_state_machine import (
    reset_current_execution_state_machine,
    set_current_execution_state_machine,
)
from app.ai.engine.tool_processor import ToolCallProcessor, _try_repair_json
from app.ai.engine.types import IntentPlan
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage


class _FakeExecutionState:
    def __init__(self, intent_plan: list[IntentPlan]) -> None:
        self.intent_plan = intent_plan
        self.readonly_tool_cache: dict[str, tuple[ToolResult, int]] = {}
        self.page_context_cache: dict[str, tuple[ToolResult, int]] = {}
        self.search_query_cache: dict[str, tuple[ToolResult, int]] = {}
        self.cache_hits: list[str] = []

    def cache_for_kind(self, kind: str) -> dict[str, tuple[ToolResult, int]]:
        if kind == "search_query":
            return self.search_query_cache
        if kind == "page_context":
            return self.page_context_cache
        return self.readonly_tool_cache

    def register_cache_hit(self, kind: str) -> None:
        self.cache_hits.append(kind)


def test_trailing_comma() -> None:
    assert _try_repair_json('{"a": 1,}') == {"a": 1}


def test_unescaped_newline() -> None:
    assert _try_repair_json('{"a": "x\ny"}') == {"a": "x\ny"}


def test_truncation() -> None:
    r = _try_repair_json('{"a": "unclosed')
    assert r == {"a": "unclosed"}


def test_parse_arguments_valid() -> None:
    args, err = ToolCallProcessor.parse_arguments(
        '{"table_name": "agents", "data": {"name": "test"}}'
    )
    assert err is None
    assert args is not None
    assert args["table_name"] == "agents"


def test_embedded_quotes() -> None:
    """DeepSeek may embed unescaped quotes inside string values."""
    raw = '{"data": {"name": "她叫"小喵"的猫", "age": 3}}'
    r = _try_repair_json(raw)
    assert r is not None
    assert r["data"]["age"] == 3
    assert "小喵" in r["data"]["name"]


def test_newlines_and_embedded_quotes() -> None:
    """Combined: literal newlines + embedded quotes."""
    raw = '{"data": {"prompt": "line1\nShe says "hello"\nline3", "ok": true}}'
    r = _try_repair_json(raw)
    assert r is not None
    assert r["data"]["ok"] is True


def test_multiline_chinese_system_prompt() -> None:
    """Simulate the typical DeepSeek failure: long Chinese system_prompt with
    literal newlines and embedded quotes."""
    raw = (
        '{"table_name": "agents", "data": {"name": "猫娘助手", '
        '"system_prompt": "你是一只可爱的猫娘。\n\n'
        "## 核心人设\n"
        '你是一只名叫"小喵"的猫娘\n'
        "- 说话时在句尾加喵~\n"
        '- 会撒娇打滚", "model_id": 2, "temperature": 0.8}}'
    )
    r = _try_repair_json(raw)
    assert r is not None
    assert r["table_name"] == "agents"
    assert r["data"]["model_id"] == 2
    assert r["data"]["temperature"] == 0.8


def test_brute_force_fallback() -> None:
    """When nothing else works, brute-force should at least produce a result."""
    raw = '{"a": "line1\nline2\nline3"}'
    r = _try_repair_json(raw)
    assert r is not None
    assert "a" in r


def test_find_pending_confirmation_injects_confirmed_for_preview_flow() -> None:
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[{
                "id": "tc_preview",
                "type": "function",
                "function": {
                    "name": "update_records",
                    "arguments": '{"table_name":"agents","confirmed":false}',
                },
            }],
        ),
        ChatMessage(
            role="tool",
            content=json.dumps({"requires_confirmation": True, "preview": {}}),
            tool_call_id="tc_preview",
        ),
    ]

    pending = ToolCallProcessor.find_pending_confirmation(messages)

    assert pending is not None
    assert pending["name"] == "update_records"
    assert pending["arguments"]["confirmed"] is True


def test_find_pending_confirmation_keeps_consent_tool_args_clean() -> None:
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[{
                "id": "tc_consent",
                "type": "function",
                "function": {
                    "name": "web_search",
                    "arguments": '{"query":"Sample Topic public info","max_results":1}',
                },
            }],
        ),
        ChatMessage(
            role="tool",
            content=json.dumps(
                {
                    "requires_confirmation": True,
                    "consent_required": True,
                    "action": "tool_consent",
                    "tool_name": "web_search",
                    "arguments": {
                        "query": "Sample Topic public info",
                        "max_results": 1,
                    },
                },
                ensure_ascii=False,
            ),
            tool_call_id="tc_consent",
        ),
    ]

    pending = ToolCallProcessor.find_pending_confirmation(messages)

    assert pending is not None
    assert pending["name"] == "web_search"
    assert pending["arguments"] == {
        "query": "Sample Topic public info",
        "max_results": 1,
    }
    assert "confirmed" not in pending["arguments"]


def test_build_pending_confirmation_payload_keeps_tool_name() -> None:
    payload = ToolCallProcessor.build_pending_confirmation_payload(
        {"action": "update", "table": "agents"},
        "ui_fill_form",
    )

    assert payload["tool_name"] == "ui_fill_form"


def test_build_confirmation_event_keeps_tool_name() -> None:
    payload = ToolCallProcessor.build_confirmation_event(
        {"action": "update", "table": "agents"},
        "ui_fill_form",
    )

    assert payload["event"] == "confirmation_request"
    assert payload["tool_name"] == "ui_fill_form"


def test_build_attachment_relay_message_returns_none_without_attachments() -> None:
    result = ToolResult(
        tool_call_id="tc_result",
        name="web_search",
        success=True,
        output="Search results ready.",
    )

    follow_up = ToolCallProcessor.build_attachment_relay_message(result)

    assert follow_up is None


def test_build_attachment_relay_message_relays_only_attachments() -> None:
    result = ToolResult(
        tool_call_id="tc_media",
        name="ui_click",
        success=True,
        attachments=[{"type": "image", "url": "https://example.com/image.png"}],
    )

    follow_up = ToolCallProcessor.build_attachment_relay_message(result)

    assert follow_up is not None
    assert follow_up.role == "user"
    assert follow_up.internal_only is True
    assert follow_up.content == ""
    assert follow_up.attachments == [{"type": "image", "url": "https://example.com/image.png"}]


def test_execute_tool_uses_all_tools_fallback_for_pending_confirmation_replay() -> None:
    class _Sandbox:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def execute(self, **kwargs):
            self.calls.append(kwargs)
            return ToolResult(
                tool_call_id=kwargs["tool_call_id"],
                name=kwargs["name"],
                success=True,
                output="ok",
            )

    async def _run() -> list[dict]:
        sandbox = _Sandbox()
        processor = ToolCallProcessor(
            sandbox=sandbox,  # type: ignore[arg-type]
            tools=[ToolDefinition(name="web_search")],
            all_tools=[
                ToolDefinition(name="web_search"),
                ToolDefinition(name="get_current_weather"),
            ],
        )

        await processor.execute_tool(
            "tc_pending",
            "get_current_weather",
            {"city": "上海"},
            conversation_id=1,
        )
        return sandbox.calls

    calls = asyncio.run(_run())

    assert len(calls) == 1
    definitions = calls[0]["definitions"]
    assert [tool.name for tool in definitions] == [
        "web_search",
        "get_current_weather",
    ]


def test_execute_tool_repairs_fetch_url_to_search_candidate() -> None:
    class _Sandbox:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def execute(self, **kwargs):
            self.calls.append(kwargs)
            return ToolResult(
                tool_call_id=kwargs["tool_call_id"],
                name=kwargs["name"],
                success=True,
                output=f"Fetched {kwargs['arguments']['url']}",
            )

    async def _run() -> tuple[list[dict], ToolResult, IntentPlan]:
        sandbox = _Sandbox()
        processor = ToolCallProcessor(
            sandbox=sandbox,  # type: ignore[arg-type]
            tools=[ToolDefinition(name="fetch_url")],
        )
        intent = IntentPlan(
            intent_id="intent-web",
            kind="web_research",
            family="web_research",
            order=1,
            user_visible_label="research",
            source_text="OpenAI news",
            allowed_tool_names=["fetch_url"],
            preferred_tool_names=["fetch_url"],
            completion_signals=["fetch_url"],
            metadata={
                "requires_fetch_url": True,
                "fetch_url_candidate_urls": [
                    "https://example.com/ai-news",
                    "https://example.com/openai",
                ],
            },
        )
        state = _FakeExecutionState([intent])
        token = set_current_execution_state_machine(state)
        try:
            result, _duration_ms = await processor.execute_tool(
                "tc_fetch",
                "fetch_url",
                {
                    "url": "https://www.reuters.com/technology/artificial-intelligence/",
                    "max_length": 5000,
                },
                conversation_id=1,
            )
        finally:
            reset_current_execution_state_machine(token)
        return sandbox.calls, result, intent

    calls, result, intent = asyncio.run(_run())

    assert len(calls) == 1
    assert calls[0]["arguments"]["url"] == "https://example.com/ai-news"
    assert result.success is True
    assert intent.metadata["fetch_url_attempted_urls"] == ["https://example.com/ai-news"]
    assert intent.metadata.get("fetch_url_blocked_urls") in (None, [])


def test_execute_tool_rotates_blocked_fetch_url_candidate() -> None:
    class _Sandbox:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def execute(self, **kwargs):
            self.calls.append(kwargs)
            url = str(kwargs["arguments"]["url"])
            if url.endswith("/blocked"):
                return ToolResult(
                    tool_call_id=kwargs["tool_call_id"],
                    name=kwargs["name"],
                    success=False,
                    error=(
                        f"HTTP 403 while fetching {url} "
                        "This page may block automated access"
                    ),
                    error_type="blocked_url",
                )
            return ToolResult(
                tool_call_id=kwargs["tool_call_id"],
                name=kwargs["name"],
                success=True,
                output=f"Fetched {url}",
            )

    async def _run() -> tuple[list[dict], ToolResult, IntentPlan]:
        sandbox = _Sandbox()
        processor = ToolCallProcessor(
            sandbox=sandbox,  # type: ignore[arg-type]
            tools=[ToolDefinition(name="fetch_url")],
        )
        intent = IntentPlan(
            intent_id="intent-web",
            kind="web_research",
            family="web_research",
            order=1,
            user_visible_label="research",
            source_text="OpenAI news",
            allowed_tool_names=["fetch_url"],
            preferred_tool_names=["fetch_url"],
            completion_signals=["fetch_url"],
            metadata={
                "requires_fetch_url": True,
                "fetch_url_candidate_urls": [
                    "https://example.com/blocked",
                    "https://example.com/openai",
                ],
            },
        )
        state = _FakeExecutionState([intent])
        token = set_current_execution_state_machine(state)
        try:
            result, _duration_ms = await processor.execute_tool(
                "tc_fetch",
                "fetch_url",
                {"url": "https://example.com/blocked", "max_length": 5000},
                conversation_id=1,
            )
        finally:
            reset_current_execution_state_machine(token)
        return sandbox.calls, result, intent

    calls, result, intent = asyncio.run(_run())

    assert [call["arguments"]["url"] for call in calls] == [
        "https://example.com/blocked",
        "https://example.com/openai",
    ]
    assert result.success is True
    assert result.output == "Fetched https://example.com/openai"
    assert intent.metadata["fetch_url_attempted_urls"] == [
        "https://example.com/blocked",
        "https://example.com/openai",
    ]
    assert intent.metadata["fetch_url_blocked_urls"] == ["https://example.com/blocked"]


def test_resolve_fetch_url_candidates_does_not_guess_without_candidates() -> None:
    selected_url, fallback_urls, requested_url = ToolCallProcessor._resolve_fetch_url_candidates(
        intent=IntentPlan(
            intent_id="intent-web",
            kind="web_research",
            family="web_research",
            order=1,
            user_visible_label="research",
            source_text="OpenAI news",
            metadata={},
        ),
        requested_url="https://example.com/guessed",
    )

    assert selected_url is None
    assert fallback_urls == []
    assert requested_url == "https://example.com/guessed"


def test_execute_tool_allows_direct_fetch_url_when_user_explicitly_provides_url() -> None:
    class _Sandbox:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def execute(self, **kwargs):
            self.calls.append(kwargs)
            return ToolResult(
                tool_call_id=kwargs["tool_call_id"],
                name=kwargs["name"],
                success=True,
                output=f"Fetched {kwargs['arguments']['url']}",
            )

    async def _run() -> tuple[list[dict], ToolResult]:
        sandbox = _Sandbox()
        processor = ToolCallProcessor(
            sandbox=sandbox,  # type: ignore[arg-type]
            tools=[ToolDefinition(name="fetch_url")],
        )
        intent = IntentPlan(
            intent_id="intent-web",
            kind="web_research",
            family="web_research",
            order=1,
            user_visible_label="research",
            source_text="Fetch this URL directly",
            allowed_tool_names=["fetch_url"],
            preferred_tool_names=["fetch_url"],
            completion_signals=["fetch_url"],
            metadata={"requires_fetch_url": False},
        )
        state = _FakeExecutionState([intent])
        token = set_current_execution_state_machine(state)
        try:
            result, _duration_ms = await processor.execute_tool(
                "tc_fetch_direct",
                "fetch_url",
                {"url": "https://example.com/direct", "max_length": 5000},
                conversation_id=1,
            )
        finally:
            reset_current_execution_state_machine(token)
        return sandbox.calls, result

    calls, result = asyncio.run(_run())

    assert len(calls) == 1
    assert calls[0]["arguments"]["url"] == "https://example.com/direct"
    assert result.success is True


def test_check_consent_treats_approved_pending_consent_as_auto_once() -> None:
    processor = ToolCallProcessor(
        sandbox=None,  # type: ignore[arg-type]
        tools=[ToolDefinition(name="get_current_weather")],
        consent_modes={"get_current_weather": "ask"},
        approved_pending_consent_tools={"get_current_weather"},
    )

    assert processor.check_consent("get_current_weather") == "auto"
    assert processor.check_consent("get_current_weather") == "auto"


def test_check_consent_auto_approves_readonly_tool_in_trusted_auto_mode() -> None:
    processor = ToolCallProcessor(
        sandbox=None,  # type: ignore[arg-type]
        tools=[ToolDefinition(name="get_current_weather")],
        consent_modes={"get_current_weather": "ask"},
        interaction_mode="trusted_auto",
    )

    assert processor.check_consent("get_current_weather", {"city": "西安"}) == "auto"


def test_check_consent_keeps_ui_write_ops_on_ask_and_auto_approves_ui_reads() -> None:
    processor = ToolCallProcessor(
        sandbox=None,  # type: ignore[arg-type]
        tools=[
            ToolDefinition(name="ui_fill_form"),
            ToolDefinition(name="ui_read_region"),
        ],
        consent_modes={
            "ui_fill_form": "ask",
            "ui_read_region": "ask",
        },
        interaction_mode="trusted_auto",
    )

    assert (
        processor.check_consent(
            "ui_fill_form",
            {"fields": [{"field": "name", "value": "Alice"}]},
        )
        == "ask"
    )
    assert (
        processor.check_consent(
            "ui_read_region",
            {"target_locator": "table-main"},
        )
        == "auto"
    )


def test_approved_pending_consent_tool_names_filters_rejected_updates() -> None:
    approved = ToolCallProcessor.approved_pending_consent_tool_names(
        [
            {"kind": "pending_consent", "tool_name": "get_current_weather"},
            {"kind": "pending_consent", "tool_name": "get_weather_forecast", "rejected": True},
            {"kind": "pending_confirmation", "tool_name": "ui_submit_form"},
        ]
    )

    assert approved == {"get_current_weather"}


def test_get_skill_info_falls_back_to_all_tools_when_tool_was_optimized_out() -> None:
    processor = ToolCallProcessor(
        sandbox=None,  # type: ignore[arg-type]
        tools=[ToolDefinition(name="web_search")],
        all_tools=[
            ToolDefinition(
                name="get_current_weather",
                source_skill_name="实时天气查询",
                source_package_name="天气组件",
            ),
        ],
    )

    skill_info = processor.get_skill_info("get_current_weather")

    assert skill_info == {
        "skill_name": "实时天气查询",
        "package_name": "天气组件",
    }
