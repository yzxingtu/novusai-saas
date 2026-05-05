"""Test type: behavioral
Regression for: 05-05-remove-online-search-capability
Scope: resolver output, deterministic intent planning, and provider payload surfaces.
Real dependencies: resolve_for_agent, SkillResolveResult sanitization, IntentPlanner,
AIProviderService config normalization, and OpenAI-compatible payload builders.
Mocked dependencies: SQLAlchemy execute stub and local adapter transport only; no
LLM/tool executor mocks.
"""

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.adapters.openai_compatible.request_payload_builders import (
    build_responses_request,
)
from app.ai.engine.intent_planner import IntentPlanner
from app.ai.skills.resolver import resolve_for_agent
from app.ai.types import ChatMessage
from app.services.ai.provider_service import AIProviderService

REMOVED_ONLINE_SEARCH_NAMES = {"web_search", "fetch_url", "web_research"}
REMOVED_PROVIDER_CONFIG_KEYS = {
    "web_search",
    "web_search_runtime",
    "hosted_web_search",
    "supports_hosted_web_search",
    "hosted_web_search_supported",
    "native_web_search_supported",
}


class _ResponsesPayloadAdapterStub:
    config: dict = {}
    provider_config: dict = {"hosted_web_search": True}

    def resolve_effective_model_request(
        self,
        *,
        model: str,
        model_config=None,
        wire_api: str | None = None,
    ) -> dict:
        _ = model_config, wire_api
        return {"upstream_model": model, "effective_params": {}}

    async def _convert_messages_to_responses_input(
        self,
        messages: list[ChatMessage],
        *,
        supports_vision: bool = True,
        supports_audio: bool = False,
        supports_video: bool = False,
    ) -> list[dict]:
        _ = supports_vision, supports_audio, supports_video
        return [
            {
                "type": "message",
                "role": message.role,
                "content": message.content,
            }
            for message in messages
        ]


@pytest.mark.asyncio
async def test_current_information_prompts_do_not_expose_online_search_tools() -> None:
    """中文: 当前信息请求不得暴露已移除的联网搜索工具。

    EN: Current-information requests must not expose removed online-search tools.
    """
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    agent = SimpleNamespace(id=1, owner_tenant_id=9)

    resolved = await resolve_for_agent(db, agent, tenant_id=9)

    resolved_tool_names = {tool.name for tool in resolved.tools}
    assert resolved_tool_names.isdisjoint(REMOVED_ONLINE_SEARCH_NAMES)
    assert set(resolved.selected_tool_names).isdisjoint(REMOVED_ONLINE_SEARCH_NAMES)
    assert set(resolved.selected_skill_names).isdisjoint(REMOVED_ONLINE_SEARCH_NAMES)

    for prompt in (
        "查一下今日AI 新闻",
        "查一下大模型排行榜 2026 水平排行！",
        "search today's AI news",
    ):
        plans = IntentPlanner.plan_turn(
            messages=[ChatMessage(role="user", content=prompt)],
            tools=resolved.tools,
            input_variables={},
            continuation_context=None,
        )

        assert [plan.kind for plan in plans] == ["direct_reply"]
        assert [plan.family for plan in plans] == ["none"]
        assert plans[0].requires_tools is False
        plan_tool_names = set(plans[0].allowed_tool_names)
        plan_tool_names.update(plans[0].preferred_tool_names)
        plan_tool_names.update(plans[0].completion_signals)
        assert plan_tool_names.isdisjoint(REMOVED_ONLINE_SEARCH_NAMES)


def test_provider_config_surfaces_strip_online_search_settings() -> None:
    """中文: 供应商配置读写面不得保留已移除的联网搜索开关。

    EN: Provider configuration surfaces must strip removed online-search flags.
    """
    validated = AIProviderService._validate_provider_payload(
        {
            "type": "openai_compatible",
            "base_url": "https://provider.example/v1",
            "config": {
                "web_search": True,
                "hosted_web_search": {"enabled": True},
                "native_web_search_supported": True,
                "reasoning_effort": "high",
            },
        }
    )

    assert validated["config"] == {"reasoning_effort": "high"}
    assert set(validated["config"]).isdisjoint(REMOVED_PROVIDER_CONFIG_KEYS)

    provider = SimpleNamespace(
        id=7,
        name="Provider",
        code="provider",
        type="openai_compatible",
        base_url="https://provider.example/v1",
        description=None,
        icon=None,
        is_active=True,
        sort_order=0,
        model_count=0,
        created_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
        config={
            "supports_hosted_web_search": True,
            "web_search_runtime": {"mode": "native"},
            "kept": "value",
        },
    )

    response = AIProviderService.to_response_schema(provider)

    assert response.config == {"kept": "value"}
    assert set(response.config or {}).isdisjoint(REMOVED_PROVIDER_CONFIG_KEYS)


@pytest.mark.asyncio
async def test_responses_payload_surface_does_not_forward_hosted_search_tools() -> None:
    """中文: Responses 请求构造不得把托管搜索工具传给供应商。

    EN: Responses request construction must not forward hosted search tools.
    """
    request = await build_responses_request(
        adapter=_ResponsesPayloadAdapterStub(),
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        tools=[
            {"type": "web_search"},
            {"type": "web_search_preview"},
            {"type": "function", "function": {"name": "crm_lookup", "parameters": {}}},
        ],
        tool_choice="required",
        kwargs={"_runtime_native_search_probe": True},
        reasoning_summary_model_prefixes=("gpt-5",),
    )

    assert request["tools"] == [
        {
            "type": "function",
            "name": "crm_lookup",
            "description": None,
            "parameters": {},
        }
    ]
    serialized = json.dumps(request, sort_keys=True)
    assert all(name not in serialized for name in REMOVED_ONLINE_SEARCH_NAMES)
