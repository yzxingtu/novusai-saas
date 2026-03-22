"""ModelRouter smart-routing tests / ModelRouter 智能路由测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.routing.router import ModelRouter
from app.ai.types import ChatMessage
from app.exceptions import BusinessException


def _make_provider(provider_id: int, code: str = "openai"):
    provider = MagicMock()
    provider.id = provider_id
    provider.code = code
    return provider


def _make_model(
    *,
    model_id: int,
    provider_id: int,
    code: str,
    tier: str,
    supports_vision: bool = False,
    supports_audio: bool = False,
    supports_video: bool = False,
    supports_function_calling: bool = False,
    context_window: int = 8192,
):
    model = MagicMock()
    model.id = model_id
    model.provider_id = provider_id
    model.provider = _make_provider(provider_id, f"provider-{provider_id}")
    model.code = code
    model.tier = tier
    model.supports_vision = supports_vision
    model.supports_audio = supports_audio
    model.supports_video = supports_video
    model.supports_function_calling = supports_function_calling
    model.context_window = context_window
    return model


def _make_agent(*, model, routing_config: dict | None = None):
    agent = MagicMock()
    agent.id = 100
    agent.model = model
    agent.model_id = model.id
    agent.routing_config = routing_config or {"enable_routing": True}
    return agent


def _patch_model_repo(monkeypatch: pytest.MonkeyPatch, repo_mock: MagicMock) -> None:
    class _RepoFactory:
        def __init__(self, db):
            self.db = db

        async def get_active_with_provider(self, model_id: int):
            return await repo_mock.get_active_with_provider(model_id)

        async def get_by_tier(
            self,
            *,
            tier: str,
            preferred_provider_id: int | None = None,
            supports_vision: bool = False,
            supports_audio: bool = False,
            supports_video: bool = False,
            supports_function_calling: bool = False,
            min_context_window: int | None = None,
        ):
            return await repo_mock.get_by_tier(
                tier=tier,
                preferred_provider_id=preferred_provider_id,
                supports_vision=supports_vision,
                supports_audio=supports_audio,
                supports_video=supports_video,
                supports_function_calling=supports_function_calling,
                min_context_window=min_context_window,
            )

    monkeypatch.setattr(
        "app.repositories.ai.model_repository.AIModelRepository",
        _RepoFactory,
    )


@pytest.mark.asyncio
async def test_route_raises_when_image_attachment_has_no_capable_model(mock_db, monkeypatch):
    repo_mock = MagicMock()
    repo_mock.get_active_with_provider = AsyncMock(return_value=None)
    repo_mock.get_by_tier = AsyncMock(return_value=None)
    _patch_model_repo(monkeypatch, repo_mock)

    agent_model = _make_model(
        model_id=1,
        provider_id=1,
        code="text-base",
        tier="fast",
    )
    agent = _make_agent(model=agent_model)
    request = SimpleNamespace(
        messages=[
            ChatMessage(
                role="user",
                content="look at this",
                attachments=[{"type": "image", "url": "https://example.com/a.png"}],
            ),
        ],
        attachments=None,
    )

    router = ModelRouter(mock_db)
    router._is_provider_healthy = AsyncMock(return_value=True)

    with pytest.raises(BusinessException):
        await router.route(agent, request, estimated_tokens=128)


@pytest.mark.asyncio
async def test_route_skips_explicit_vision_model_without_function_calling(
    mock_db,
    monkeypatch,
):
    explicit_model = _make_model(
        model_id=77,
        provider_id=2,
        code="vision-no-fc",
        tier="standard",
        supports_vision=True,
        supports_function_calling=False,
    )
    fallback_model = _make_model(
        model_id=88,
        provider_id=3,
        code="vision-with-fc",
        tier="standard",
        supports_vision=True,
        supports_function_calling=True,
    )

    repo_mock = MagicMock()
    repo_mock.get_active_with_provider = AsyncMock(return_value=explicit_model)
    repo_mock.get_by_tier = AsyncMock(return_value=fallback_model)
    _patch_model_repo(monkeypatch, repo_mock)

    agent_model = _make_model(
        model_id=1,
        provider_id=1,
        code="text-base",
        tier="fast",
    )
    agent = _make_agent(
        model=agent_model,
        routing_config={"enable_routing": True, "vision_model_id": 77},
    )
    request = SimpleNamespace(
        messages=[
            ChatMessage(
                role="user",
                content="analyze this screenshot",
                attachments=[{"type": "image", "url": "https://example.com/a.png"}],
            ),
        ],
        attachments=None,
    )

    router = ModelRouter(mock_db)
    router._is_provider_healthy = AsyncMock(return_value=True)

    result = await router.route(
        agent,
        request,
        estimated_tokens=256,
        tools=[{"name": "browser"}],
    )

    assert result.model_id == 88
    assert result.reason == "vision:tier_fallback"
    assert result.is_overridden is True


@pytest.mark.asyncio
async def test_route_raises_when_long_context_has_no_suitable_model(
    mock_db,
    monkeypatch,
):
    explicit_model = _make_model(
        model_id=99,
        provider_id=2,
        code="lc-too-small",
        tier="premium",
        context_window=12_000,
    )
    repo_mock = MagicMock()
    repo_mock.get_active_with_provider = AsyncMock(return_value=explicit_model)
    repo_mock.get_by_tier = AsyncMock(return_value=None)
    _patch_model_repo(monkeypatch, repo_mock)

    agent_model = _make_model(
        model_id=1,
        provider_id=1,
        code="base-small",
        tier="standard",
        context_window=8_000,
    )
    agent = _make_agent(
        model=agent_model,
        routing_config={
            "enable_routing": True,
            "long_context_model_id": 99,
            "long_context_threshold": 1_000,
        },
    )
    request = SimpleNamespace(
        messages=[ChatMessage(role="user", content="please summarize")],
        attachments=None,
    )

    router = ModelRouter(mock_db)
    router._is_provider_healthy = AsyncMock(return_value=True)

    with pytest.raises(BusinessException):
        await router.route(agent, request, estimated_tokens=20_000)


@pytest.mark.asyncio
async def test_route_treats_message_level_file_attachment_as_attachment_for_complexity(
    mock_db,
    monkeypatch,
):
    fast_model = _make_model(
        model_id=2,
        provider_id=2,
        code="fast-model",
        tier="fast",
    )
    standard_model = _make_model(
        model_id=3,
        provider_id=3,
        code="standard-model",
        tier="standard",
    )

    async def _get_by_tier(**kwargs):
        tier = kwargs["tier"]
        if tier == "standard":
            return standard_model
        if tier == "fast":
            return fast_model
        return None

    repo_mock = MagicMock()
    repo_mock.get_active_with_provider = AsyncMock(return_value=None)
    repo_mock.get_by_tier = AsyncMock(side_effect=_get_by_tier)
    _patch_model_repo(monkeypatch, repo_mock)

    agent_model = _make_model(
        model_id=1,
        provider_id=1,
        code="base-model",
        tier="fast",
    )
    agent = _make_agent(model=agent_model)
    request = SimpleNamespace(
        messages=[
            ChatMessage(
                role="user",
                content="read this",
                attachments=[{"type": "file", "url": "https://example.com/readme.pdf"}],
            ),
        ],
        attachments=None,
    )

    router = ModelRouter(mock_db)
    router._is_provider_healthy = AsyncMock(return_value=True)

    result = await router.route(agent, request, estimated_tokens=128)

    assert result.model_id == 3
    assert result.tier == "standard"
    assert result.reason == "complexity:medium"
